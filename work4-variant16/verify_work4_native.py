# -*- coding: utf-8 -*-
"""Strict reopen/rebuild/parametric acceptance for Work 4 variant 16."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import math
import sys

import pythoncom

from work4_common import *

HERE = Path(__file__).resolve().parent
INNER = OUT / "Work4_V16_InnerDoubleRing.m3d"
CUP_L = OUT / "Work4_V16_OuterCup_L.m3d"
CUP_R = OUT / "Work4_V16_OuterCup_R.m3d"
ROLLER = OUT / "Work4_V16_TaperRoller.m3d"
CAGE = OUT / "Work4_V16_CageHalf.m3d"
RIVET = OUT / "Work4_V16_Rivet.m3d"
ASSEMBLY = OUT / "Work4_V16_Bearing.a3d"
REPORT = OUT / "verification.txt"
MANIFEST = OUT / "native-manifest.json"
ALL_NATIVE = (INNER, CUP_L, CUP_R, ROLLER, CAGE, RIVET, ASSEMBLY)


def open_model(kompas, path):
    doc = require(kompas.Document3D(), f"{path.name}: Document3D")
    require(doc.Open(str(path), False), f"{path.name}: Open")
    require(doc.RebuildDocument(), f"{path.name}: RebuildDocument")
    return doc


def enumerate_parts(doc):
    coll = require(doc.PartCollection(True), "PartCollection(True)")
    out = []
    seen = set()
    count = int(coll.GetCount())
    for idx in list(range(count)) + list(range(1, count+1)):
        try:
            p = coll.GetByIndex(idx)
        except Exception:
            p = None
        if not p:
            continue
        fn = part_filename(p)
        try:
            key = (fn.lower(), int(p.reference))
        except Exception:
            key = (fn.lower(), id(p))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def group_parts(doc):
    out = {}
    for p in enumerate_parts(doc):
        name = Path(part_filename(p)).name
        out.setdefault(name, []).append(p)
    return out


def mass(part):
    value = float(part.GetMass())
    require(math.isfinite(value) and value > 0.0, f"Invalid mass for {part_filename(part)}: {value}")
    return value


def var_snapshot(part):
    return {name: value for name, value in list_vars(part)}


def assert_master_geometry(top, const):
    coll = require(top.EntityCollection(const.o3d_sketch), "Assembly sketch collection")
    found = None
    for i in range(int(coll.GetCount())):
        sk = coll.GetByIndex(i)
        if not sk:
            continue
        for attr in ("name", "Name"):
            try:
                name = str(getattr(sk, attr))
                if name == "MASTER_GEOMETRY_V16":
                    found = sk
                    break
            except Exception:
                pass
        if found:
            break
    require(found, "MASTER_GEOMETRY_V16 not found after reopen")
    return found


def assert_component_contract(groups, n):
    require(len(groups.get(INNER.name, [])) == 1, "Variant 16 requires one double inner ring")
    require(len(groups.get(CUP_L.name, [])) == 1, "Variant 16 requires left outer cup")
    require(len(groups.get(CUP_R.name, [])) == 1, "Variant 16 requires right outer cup")
    require(len(groups.get(ROLLER.name, [])) == 2*n, "Variant 16 requires two roller rows")
    require(len(groups.get(CAGE.name, [])) == 4, "Variant 16 requires two two-half cages")
    require(len(groups.get(RIVET.name, [])) == 2*n, "Variant 16 rivet count mismatch")


def set_T(top, value):
    t = get_var(top, "T")
    set_var_expression(t, f"{float(value):.12g}")
    require(top.RebuildModel(), f"TopPart RebuildModel after T={value}")
    return var_value(t)


def component_width(part):
    return var_value(get_var(part, "W"))


def state(doc, const, n):
    top = require(doc.GetPart(const.pTop_Part), "Assembly top part")
    assert_master_geometry(top, const)
    groups = group_parts(doc)
    assert_component_contract(groups, n)
    vars_ = var_snapshot(top)
    required_vars = {
        "D","d","T","C","B","R","b_rol","d_rol","N_rol","S","z","alpha",
        "D1","D2","cage_h","cage_cell_d","rivet_pitch_d","rivet_angle_offset","rivet_d"
    }
    require(required_vars.issubset(set(vars_)),
            f"Assembly variables missing: {sorted(required_vars-set(vars_))}")
    inner = groups[INNER.name][0]
    cup_l = groups[CUP_L.name][0]
    cup_r = groups[CUP_R.name][0]
    return {
        "top": top,
        "groups": groups,
        "vars": vars_,
        "inner_mass": mass(inner),
        "cup_l_mass": mass(cup_l),
        "cup_r_mass": mass(cup_r),
        "inner_W": component_width(inner),
        "cup_l_W": component_width(cup_l),
        "cup_r_W": component_width(cup_r),
    }


def close(doc):
    try:
        doc.close()
    except Exception:
        pass


def relclose(a, b, rel=1e-6, abs_=1e-6):
    return abs(a-b) <= max(abs_, rel*max(abs(a),abs(b),1.0))


def main():
    pythoncom.CoInitialize()
    const = constants()
    kompas = get_kompas5()
    _, val = read_params()
    n = int(val("N_rol"))
    nominal_T = val("T")
    changed_T = val("rebuild_test_T")

    for p in ALL_NATIVE:
        native_file(p)
    source_hashes = {p.name: sha256(p) for p in (INNER,CUP_L,CUP_R,ROLLER,CAGE,RIVET)}

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(manifest["variant"] == 16, "Manifest variant mismatch")
    require(manifest["topology"]["double_inner_ring"] == 1, "Manifest topology mismatch")
    require(manifest["topology"]["outer_cups"] == 2, "Manifest topology mismatch")
    require(manifest["topology"]["roller_rows"] == 2, "Manifest topology mismatch")

    # Independent reopen of every M3D first.
    reopened_details = []
    for p in (INNER,CUP_L,CUP_R,ROLLER,CAGE,RIVET):
        d = open_model(kompas, p)
        require(d.IsDetail(), f"{p.name}: reopened as non-detail")
        require(d.GetLastFeature(), f"{p.name}: no persisted 3D feature")
        top = require(d.GetPart(const.pTop_Part), f"{p.name}: top part")
        ext = var_snapshot(top)
        require(ext, f"{p.name}: no external variables")
        reopened_details.append((p.name, sorted(ext)))
        close(d)

    # Nominal assembly state from disk.
    asm = open_model(kompas, ASSEMBLY)
    require(not asm.IsDetail(), "A3D reopened as detail")
    s0 = state(asm, const, n)
    require(relclose(s0["vars"]["T"], nominal_T), f"Nominal T drift: {s0['vars']['T']}")
    require(relclose(s0["vars"]["B"], nominal_T/2.0), "B != T/2")
    require(relclose(s0["vars"]["C"], nominal_T), "C != T")
    require(relclose(s0["vars"]["z"], (val("d")+val("D"))/4.0), "z formula mismatch")
    require(relclose(s0["vars"]["D1"], 102.0), "D1 ROUND formula mismatch")
    require(relclose(s0["vars"]["D2"], 91.0), "D2 ROUND formula mismatch")
    require(relclose(s0["inner_W"], nominal_T), "Inner ring W is not linked to T")
    require(relclose(s0["cup_l_W"], nominal_T/2.0), "Left cup W is not linked to T/2")
    require(relclose(s0["cup_r_W"], nominal_T/2.0), "Right cup W is not linked to T/2")

    baseline = {
        "inner": s0["inner_mass"],
        "cup_l": s0["cup_l_mass"],
        "cup_r": s0["cup_r_mass"],
    }

    # Strict native parametric test: change only top-level T.
    require(relclose(set_T(s0["top"], changed_T), changed_T), "Could not set T test value")
    require(asm.RebuildDocument(), "Assembly rebuild after T mutation")
    s1 = state(asm, const, n)
    require(relclose(s1["vars"]["T"], changed_T), "T mutation not visible")
    require(relclose(s1["vars"]["B"], changed_T/2.0), "Dependent B did not change")
    require(relclose(s1["vars"]["C"], changed_T), "Dependent C did not change")
    require(relclose(s1["inner_W"], changed_T), "Inner W did not receive T")
    require(relclose(s1["cup_l_W"], changed_T/2.0), "Cup L W did not receive T/2")
    require(relclose(s1["cup_r_W"], changed_T/2.0), "Cup R W did not receive T/2")

    deltas = {
        "inner": abs(s1["inner_mass"]-baseline["inner"]),
        "cup_l": abs(s1["cup_l_mass"]-baseline["cup_l"]),
        "cup_r": abs(s1["cup_r_mass"]-baseline["cup_r"]),
    }
    require(all(v > 1e-5 for v in deltas.values()),
            f"T changed variables but not physical ring masses: {deltas}")

    require(asm.Save(), "Save changed-T assembly")
    close(asm)

    # Save/Close/Reopen while changed - persistence proof.
    asm_changed = open_model(kompas, ASSEMBLY)
    sc = state(asm_changed, const, n)
    require(relclose(sc["vars"]["T"], changed_T), "Changed T did not persist after reopen")
    require(relclose(sc["inner_W"], changed_T), "Changed inner W did not persist")
    require(relclose(sc["cup_l_W"], changed_T/2.0), "Changed cup W did not persist")
    require(not relclose(sc["inner_mass"], baseline["inner"], rel=1e-7),
            "Changed physical inner-ring mass lost after reopen")

    # Restore nominal through the same controlling variable, no file regeneration.
    require(relclose(set_T(sc["top"], nominal_T), nominal_T), "Could not restore T")
    require(asm_changed.RebuildDocument(), "Assembly rebuild after T restore")
    sr = state(asm_changed, const, n)
    require(relclose(sr["vars"]["T"], nominal_T), "T did not restore")
    require(relclose(sr["vars"]["B"], nominal_T/2.0), "B did not restore")
    require(relclose(sr["inner_W"], nominal_T), "Inner W did not restore")
    require(relclose(sr["cup_l_W"], nominal_T/2.0), "Cup L W did not restore")
    require(relclose(sr["cup_r_W"], nominal_T/2.0), "Cup R W did not restore")
    require(relclose(sr["inner_mass"], baseline["inner"]), "Inner mass did not restore")
    require(relclose(sr["cup_l_mass"], baseline["cup_l"]), "Cup L mass did not restore")
    require(relclose(sr["cup_r_mass"], baseline["cup_r"]), "Cup R mass did not restore")
    require(asm_changed.Save(), "Save nominal-restored assembly")
    close(asm_changed)

    # Final disk reopen.
    final = open_model(kompas, ASSEMBLY)
    sf = state(final, const, n)
    require(relclose(sf["vars"]["T"], nominal_T), "Final reopened T not nominal")
    require(relclose(sf["inner_mass"], baseline["inner"]), "Final inner mass drift")
    require(relclose(sf["cup_l_mass"], baseline["cup_l"]), "Final cup L mass drift")
    require(relclose(sf["cup_r_mass"], baseline["cup_r"]), "Final cup R mass drift")
    close(final)

    # Assembly-scoped overrides must not mutate source M3D files.
    final_source_hashes = {p.name: sha256(p) for p in (INNER,CUP_L,CUP_R,ROLLER,CAGE,RIVET)}
    require(final_source_hashes == source_hashes,
            "Source M3D changed during assembly-scoped parametric rebuild test")

    for p in ALL_NATIVE:
        native_file(p)

    lines = [
        "VARIANT16_SOURCE_TOPOLOGY_REOPEN_PASS",
        f"DETAILS_REOPENED={reopened_details!r}",
        "MASTER_GEOMETRY_REOPEN_PASS",
        "ASSEMBLY_VARIABLE_SYSTEM_REOPEN_PASS",
        "ONE_DOUBLE_INNER_RING_PASS",
        "TWO_OUTER_CUPS_PASS",
        f"TWO_ROLLER_ROWS_{n}_EACH_PASS",
        "TWO_TWO_HALF_CAGES_PASS",
        "EXTERNAL_COMPONENT_VARIABLE_LINKS_PASS",
        f"T_NOMINAL={nominal_T:.9f}",
        f"T_TEST={changed_T:.9f}",
        f"INNER_MASS_NOMINAL={baseline['inner']:.12f}",
        f"INNER_MASS_CHANGED={s1['inner_mass']:.12f}",
        f"CUP_L_MASS_NOMINAL={baseline['cup_l']:.12f}",
        f"CUP_L_MASS_CHANGED={s1['cup_l_mass']:.12f}",
        f"CUP_R_MASS_NOMINAL={baseline['cup_r']:.12f}",
        f"CUP_R_MASS_CHANGED={s1['cup_r_mass']:.12f}",
        f"PHYSICAL_MASS_DELTAS={deltas!r}",
        "MAIN_VARIABLE_T_CHANGE_PASS",
        "DEPENDENT_VARIABLES_RECALCULATED_PASS",
        "COMPONENT_EXTERNAL_VARIABLES_RECALCULATED_PASS",
        "PHYSICAL_GEOMETRY_CHANGE_PASS",
        "CHANGED_STATE_SAVE_CLOSE_REOPEN_PASS",
        "MAIN_VARIABLE_T_RESTORE_PASS",
        "PHYSICAL_GEOMETRY_RESTORE_PASS",
        "SOURCE_M3D_SHA_UNCHANGED_PASS",
        "FINAL_NOMINAL_REOPEN_PASS",
    ]
    for p in ALL_NATIVE:
        lines.append(f"SHA256 {p.name} {sha256(p)}")
    lines.append("RESULT=PASS_NATIVE_WORK4_VARIANT16_REOPEN_REBUILD_PARAMETRIC")
    REPORT.write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        OUT.mkdir(parents=True, exist_ok=True)
        REPORT.write_text("RESULT=FAIL_NATIVE_WORK4_VARIANT16\n"+repr(exc)+"\n",
                          encoding="utf-8")
        print(REPORT.read_text(encoding="utf-8"), file=sys.stderr)
        raise
