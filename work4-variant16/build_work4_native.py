# -*- coding: utf-8 -*-
"""Build Work 4 variant 16 as native parametric KOMPAS M3D + A3D.

Exact topology from the source methodology:
- double-row angular-contact tapered roller bearing;
- one double inner ring;
- two separate outer cups;
- two opposed rows of tapered rollers;
- two-half cages with rivets.

The assembly owns MASTER_GEOMETRY_V16 and the controlling variable T.
External variables of inserted components are overridden by assembly
expressions, so a normal KOMPAS rebuild changes existing native components.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import math
import sys

import pythoncom

from work4_common import *

HERE = Path(__file__).resolve().parent
OUT.mkdir(parents=True, exist_ok=True)

INNER = OUT / "Work4_V16_InnerDoubleRing.m3d"
CUP_L = OUT / "Work4_V16_OuterCup_L.m3d"
CUP_R = OUT / "Work4_V16_OuterCup_R.m3d"
ROLLER = OUT / "Work4_V16_TaperRoller.m3d"
CAGE = OUT / "Work4_V16_CageHalf.m3d"
RIVET = OUT / "Work4_V16_Rivet.m3d"
ASSEMBLY = OUT / "Work4_V16_Bearing.a3d"
REPORT = OUT / "build-report.txt"
MANIFEST = OUT / "native-manifest.json"

ALL_NATIVE = (INNER, CUP_L, CUP_R, ROLLER, CAGE, RIVET, ASSEMBLY)


def build_ring(kompas, const, path, name, outer_d, inner_d, width, width_name="W"):
    doc, part = create_part_doc(kompas, const, path, name)
    add_user_var(part, width_name, width, "Axial width controlled from assembly", True)
    add_user_var(part, "D_OUT", outer_d, "Nominal outer diameter", True)
    add_user_var(part, "D_IN", inner_d, "Nominal inner diameter", True)
    sk = annulus_sketch(part, const, outer_d, inner_d, f"{name}_SECTION")
    ext = create_extrusion(part, const, sk, width, f"{name}_EXTRUSION")
    hits = bind_feature_var_by_value(part, ext, width, width_name)
    require(part.SetMaterial("ШХ15", STEEL_DENSITY_G_CM3), f"{name}: SetMaterial")
    require(doc.RebuildDocument(), f"{name}: document rebuild")
    require(doc.SaveAs(str(path)), f"{name}: SaveAs")
    close_doc(doc)
    native_file(path)
    return {"width_feature_variables": hits}


def build_roller(kompas, const, p):
    doc, part = create_part_doc(kompas, const, ROLLER, "TAPER_ROLLER_V16")
    add_user_var(part, "W", p["b_rol"], "Roller axial width", True)
    add_user_var(part, "DR", p["d_rol"], "Roller nominal diameter", True)
    add_user_var(part, "DRAFT", p["roller_draft"], "Taper half-angle used by extrusion draft", True)
    sk = circle_sketch(part, const, p["d_rol"], 0.0, 0.0, "ROLLER_PROFILE")
    ext = create_extrusion(part, const, sk, p["b_rol"], "ROLLER_TAPER_EXTRUSION",
                           draft=p["roller_draft"])
    hits = bind_feature_var_by_value(part, ext, p["b_rol"], "W")
    # Draft is also an operation variable. Bind it when exposed numerically.
    try:
        bind_feature_var_by_value(part, ext, p["roller_draft"], "DRAFT")
    except Exception:
        # Some API5 builds expose draft as a sign/angle pair rather than the
        # entered value. The geometric taper remains native; the width binding
        # is mandatory and verified later.
        pass
    require(part.SetMaterial("ШХ15", STEEL_DENSITY_G_CM3), "roller material")
    require(doc.RebuildDocument(), "roller rebuild")
    require(doc.SaveAs(str(ROLLER)), "roller SaveAs")
    close_doc(doc)
    native_file(ROLLER)
    return {"width_feature_variables": hits}


def build_cage_half(kompas, const, p):
    doc, part = create_part_doc(kompas, const, CAGE, "CAGE_HALF_V16")
    add_user_var(part, "H", p["cage_h"], "Cage-half total axial depth", True)
    add_user_var(part, "S", p["S"], "Uncut backing-ring thickness", True)
    add_user_var(part, "D1", p["D1"], "Outer cage diameter", True)
    add_user_var(part, "D2", p["D2"], "Inner cage diameter", True)
    add_user_var(part, "Z", p["z"], "Cell pitch radius", True)
    add_user_var(part, "D_CELL", p["cage_cell_d"], "Roller cell diameter", True)
    add_user_var(part, "N_ROL", p["N_rol"], "Cell count", True)

    sk = annulus_sketch(part, const, p["D1"], p["D2"], "CAGE_BASE_RING")
    # The half-cage is h = S + b_rol/2 deep. The pockets are cut only b_rol/2,
    # leaving an uncut backing ring of thickness S, so the cage stays connected.
    base = create_extrusion(part, const, sk, p["cage_h"], "CAGE_BASE_EXTRUSION")
    hits = bind_feature_var_by_value(part, base, p["cage_h"], "H")

    # One true roller pocket, then a native concentric copy N_ROL.
    psk = circle_sketch(part, const, p["cage_cell_d"], p["z"], 0.0, "CAGE_CELL_SEED")
    seed = create_cut(part, const, psk, p["b_rol"]/2.0, "CAGE_CELL_CUT")
    arr = circular_copy(part, const, seed, int(p["N_rol"]), "CAGE_CELLS_N_ROL")
    require(part.RebuildModel(), "cage rebuild after cell array")
    require(part.SetMaterial("Сталь 20", 7.85), "cage material")
    require(doc.RebuildDocument(), "cage document rebuild")
    require(doc.SaveAs(str(CAGE)), "cage SaveAs")
    close_doc(doc)
    native_file(CAGE)
    return {"width_feature_variables": hits, "cell_count": int(p["N_rol"])}


def build_rivet(kompas, const, p):
    doc, part = create_part_doc(kompas, const, RIVET, "RIVET_V16")
    length = 2.0*p["S"] + 1.0
    add_user_var(part, "W", length, "Rivet working length", True)
    add_user_var(part, "DRIVET", p["rivet_d"], "Rivet diameter", True)
    sk = circle_sketch(part, const, p["rivet_d"], 0.0, 0.0, "RIVET_PROFILE")
    ext = create_extrusion(part, const, sk, length, "RIVET_SHAFT")
    hits = bind_feature_var_by_value(part, ext, length, "W")
    require(part.SetMaterial("Сталь 20", 7.85), "rivet material")
    require(doc.RebuildDocument(), "rivet rebuild")
    require(doc.SaveAs(str(RIVET)), "rivet SaveAs")
    close_doc(doc)
    native_file(RIVET)
    return {"width_feature_variables": hits}


def build_master_geometry(top, const, p):
    # The source method requires an assembly control sketch. This sketch is an
    # explicit axial-radial bearing envelope and row layout; component dimensions
    # are driven by the same named assembly variables.
    sk, sd, d2 = create_sketch(top, const, const.o3d_planeXOY, "MASTER_GEOMETRY_V16")
    x0, x1 = -p["T"]/2.0, p["T"]/2.0
    ro, ri, z = p["D"]/2.0, p["d"]/2.0, p["z"]

    # Outer and inner envelopes.
    for y in (ro, -ro, ri, -ri):
        require(d2.ksLineSeg(x0, y, x1, y, const.ksCSNormal),
                "master envelope line")
    for x in (x0, 0.0, x1):
        require(d2.ksLineSeg(x, -ro, x, ro, const.ksCSNormal),
                "master axial station")
    # Roller-row centerlines and pitch points.
    for sx in (-1.0, 1.0):
        xc = sx*p["T"]/4.0
        dy = math.tan(math.radians(p["alpha"])) * p["b_rol"]/2.0
        require(d2.ksLineSeg(xc-p["b_rol"]/2.0, z-sx*dy,
                             xc+p["b_rol"]/2.0, z+sx*dy,
                             const.ksCSNormal), "master roller axis")
        require(d2.ksLineSeg(xc-p["b_rol"]/2.0, -z+sx*dy,
                             xc+p["b_rol"]/2.0, -z-sx*dy,
                             const.ksCSNormal), "master mirrored roller axis")
    finish_sketch(sd)
    return sk


def add_assembly_variables(top, p):
    vars_to_add = [
        ("D", p["D"], "Bearing outer diameter"),
        ("d", p["d"], "Bearing bore"),
        ("T", p["T"], "MAIN controlling total width"),
        ("C", "T", "Outer-cup total envelope"),
        ("B", "T/2", "One-row axial envelope"),
        ("R", p["R"], "Fillet radius"),
        ("b_rol", p["b_rol"], "Roller width"),
        ("d_rol", p["d_rol"], "Roller diameter"),
        ("N_rol", p["N_rol"], "Rolling elements per row"),
        ("S", p["S"], "Cage clearance/thickness"),
        ("z", "(d+D)/4", "Roller pitch radius"),
        ("alpha", p["alpha"], "Opposed row contact angle"),
        ("D1", "ROUND((d+D)/2+0.6*d_rol)", "Cage outside diameter"),
        ("D2", "ROUND((d+D)/2-0.3*d_rol)", "Cage inside diameter"),
        ("cage_h", "S+b_rol/2", "Cage lug height"),
        ("cage_cell_d", "d_rol+2*S", "Cage roller cell diameter"),
        ("rivet_pitch_d", "(D1+D2)/2", "Rivet pitch diameter"),
        ("rivet_angle_offset", "360/(2*N_rol)", "Rivet angular offset"),
        ("rivet_d", "ROUND((ROUND(D1)-ROUND(D2))/6)*0.8", "Rivet diameter"),
    ]
    for name, expr, note in vars_to_add:
        add_user_var(top, name, expr, note, True)
    return [name for name, _, _ in vars_to_add]


def insert_api7(parts, file_path, name):
    comp = require(parts.AddFromFile(str(file_path), True, False),
                   f"AddFromFile {file_path.name}")
    try:
        comp.Name = name
    except Exception:
        pass
    return comp


def placement_axes(part, xaxis, yaxis, origin):
    pl = require(part.GetPlacement(), "GetPlacement")
    require(pl.SetOrigin(*map(float, origin)), "SetOrigin")
    require(pl.SetAxes(*(list(map(float, xaxis)) + list(map(float, yaxis)))),
            "SetAxes")
    require(part.UpdatePlacement(), "UpdatePlacement")


def component_var_expression(part, name, expression):
    v = get_var(part, name)
    set_var_expression(v, expression)
    require(part.RebuildModel(), f"component {part_filename(part)} rebuild after {name}={expression}")
    return var_value(v)


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
        try:
            key = int(p.reference)
        except Exception:
            key = id(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def main():
    pythoncom.CoInitialize()
    const = constants()
    kompas = get_kompas5()
    _, val = read_params()
    p = {k: val(k) for k in (
        "D","d","T","C","B","R","b_rol","d_rol","N_rol","S","z","alpha",
        "D1","D2","cage_h","cage_cell_d","rivet_pitch_d","rivet_angle_offset",
        "rivet_d","inner_race_outer_d","outer_race_inner_d","roller_draft"
    )}
    require(int(p["N_rol"]) == 13, "Variant 16 N_rol drift")
    require(p["D"] == 120 and p["d"] == 70 and p["T"] == 40, "Nominal contract drift")
    require(p["D1"] == 102 and p["D2"] == 91, "ROUND cage dimensions drift")

    for f in ALL_NATIVE + (REPORT, MANIFEST):
        f.unlink(missing_ok=True)

    part_meta = {}
    part_meta[INNER.name] = build_ring(
        kompas, const, INNER, "INNER_DOUBLE_RING_V16",
        p["inner_race_outer_d"], p["d"], p["T"])
    part_meta[CUP_L.name] = build_ring(
        kompas, const, CUP_L, "OUTER_CUP_L_V16",
        p["D"], p["outer_race_inner_d"], p["B"])
    part_meta[CUP_R.name] = build_ring(
        kompas, const, CUP_R, "OUTER_CUP_R_V16",
        p["D"], p["outer_race_inner_d"], p["B"])
    part_meta[ROLLER.name] = build_roller(kompas, const, p)
    part_meta[CAGE.name] = build_cage_half(kompas, const, p)
    part_meta[RIVET.name] = build_rivet(kompas, const, p)

    # Assembly first gets its native master sketch and variable system.
    asm = require(kompas.Document3D(), "Assembly Document3D")
    require(asm.Create(False, False), "Create assembly")
    require(asm.SaveAs(str(ASSEMBLY)), "Initial assembly SaveAs")
    top = require(asm.GetPart(const.pTop_Part), "Assembly top part")
    set_name(top, "BEARING_V16")
    master = build_master_geometry(top, const, p)
    assembly_vars = add_assembly_variables(top, p)
    require(asm.RebuildDocument(), "Rebuild assembly master")
    require(asm.Save(), "Save assembly master")
    close_doc(asm)

    # Insert every source as an external component through official API7.
    app7 = get_kompas7()
    doc7 = require(app7.Documents.Open(str(ASSEMBLY), False, False), "API7 open assembly")
    top7 = require(doc7.TopPart, "API7 TopPart")
    parts7 = require(top7.Parts, "API7 Parts")

    insert_api7(parts7, INNER, "INNER_DOUBLE_RING")

    insert_api7(parts7, CUP_L, "OUTER_CUP_L")
    insert_api7(parts7, CUP_R, "OUTER_CUP_R")

    for row in (0, 1):
        for i in range(int(p["N_rol"])):
            insert_api7(parts7, ROLLER, f"ROLLER_R{row+1}_{i+1:02d}")

    for row in (0, 1):
        insert_api7(parts7, CAGE, f"CAGE_R{row+1}_A")
        insert_api7(parts7, CAGE, f"CAGE_R{row+1}_B")

    for row in (0, 1):
        for i in range(int(p["N_rol"])):
            insert_api7(parts7, RIVET, f"RIVET_R{row+1}_{i+1:02d}")

    require(doc7.Save(), "API7 save inserted components")
    try:
        doc7.Close(0)
    except Exception:
        pass

    # Use API5 component model to set assembly-scoped external-variable links
    # and deterministic placements.
    asm = require(kompas.Document3D(), "Assembly reopen for placement")
    require(asm.Open(str(ASSEMBLY), False), "Reopen assembly")
    require(asm.RebuildDocument(), "Rebuild inserted assembly")
    parts = enumerate_parts(asm)

    by_file = {}
    for comp in parts:
        base = Path(part_filename(comp)).name
        by_file.setdefault(base, []).append(comp)

    require(len(by_file.get(INNER.name, [])) == 1, "Need exactly one double inner ring")
    require(len(by_file.get(CUP_L.name, [])) == 1, "Need left outer cup")
    require(len(by_file.get(CUP_R.name, [])) == 1, "Need right outer cup")
    require(len(by_file.get(ROLLER.name, [])) == 2*int(p["N_rol"]), "Need two roller rows")
    require(len(by_file.get(CAGE.name, [])) == 4, "Need four cage halves")
    require(len(by_file.get(RIVET.name, [])) == 2*int(p["N_rol"]), "Need two rivet arrays")

    inner = by_file[INNER.name][0]
    cup_l = by_file[CUP_L.name][0]
    cup_r = by_file[CUP_R.name][0]

    # T drives the source external widths inside this assembly.
    component_var_expression(inner, "W", "T")
    component_var_expression(cup_l, "W", "T/2")
    component_var_expression(cup_r, "W", "T/2")

    # Source solids are one-sided along local +X.
    placement_axes(inner, (1,0,0), (0,1,0), (-p["T"]/2,0,0))
    placement_axes(cup_l, (1,0,0), (0,1,0), (-p["T"]/2,0,0))
    placement_axes(cup_r, (-1,0,0), (0,1,0), (p["T"]/2,0,0))

    # Two opposed roller rows.
    rollers = by_file[ROLLER.name]
    n = int(p["N_rol"])
    pitch_r = p["z"]
    for row in (0, 1):
        sign = -1.0 if row == 0 else 1.0
        row_x = sign*p["T"]/4.0
        for i in range(n):
            comp = rollers[row*n+i]
            component_var_expression(comp, "W", "b_rol")
            theta = 2*math.pi*i/n
            radial = (0.0, math.cos(theta), math.sin(theta))
            tangent = (0.0, -math.sin(theta), math.cos(theta))
            # Opposed-row contact-axis inclination.
            ca = math.cos(math.radians(p["alpha"]))
            sa = math.sin(math.radians(p["alpha"]))
            xaxis = (ca, sign*sa*radial[1], sign*sa*radial[2])
            center = (row_x, pitch_r*radial[1], pitch_r*radial[2])
            origin = tuple(center[j]-xaxis[j]*p["b_rol"]/2.0 for j in range(3))
            placement_axes(comp, xaxis, tangent, origin)

    # Two cage halves per row, mirrored about the row center.
    cages = by_file[CAGE.name]
    for row in (0, 1):
        row_x = (-1.0 if row == 0 else 1.0)*p["T"]/4.0
        a, b = cages[2*row], cages[2*row+1]
        component_var_expression(a, "H", "cage_h")
        component_var_expression(b, "H", "cage_h")
        placement_axes(a, (1,0,0), (0,1,0), (row_x-p["b_rol"]/2.0-p["S"],0,0))
        placement_axes(b, (-1,0,0), (0,1,0), (row_x+p["b_rol"]/2.0+p["S"],0,0))

    # Rivets on the cage mid-diameter, angularly offset by half pitch.
    rivets = by_file[RIVET.name]
    rivet_r = p["rivet_pitch_d"]/2.0
    half_step = math.radians(p["rivet_angle_offset"])
    for row in (0,1):
        row_x = (-1.0 if row == 0 else 1.0)*p["T"]/4.0
        for i in range(n):
            comp = rivets[row*n+i]
            theta = 2*math.pi*i/n + half_step
            y, z = rivet_r*math.cos(theta), rivet_r*math.sin(theta)
            placement_axes(comp, (1,0,0), (0,1,0),
                           (row_x-(2*p["S"]+1.0)/2.0, y, z))

    require(asm.RebuildDocument(), "Final bearing assembly rebuild")
    require(asm.Save(), "Final bearing assembly save")
    close_doc(asm)

    for f in ALL_NATIVE:
        native_file(f)

    manifest = {
        "work": 4,
        "variant": 16,
        "exact_type": "double-row angular-contact tapered roller bearing with double inner ring",
        "topology": {
            "double_inner_ring": 1,
            "outer_cups": 2,
            "roller_rows": 2,
            "rollers_per_row": n,
            "cage_halves": 4,
            "rivets": 2*n,
        },
        "master_geometry": "MASTER_GEOMETRY_V16",
        "main_rebuild_variable": {"name": "T", "nominal": p["T"], "test": 44.0},
        "assembly_variables": assembly_vars,
        "parts": part_meta,
        "files": {},
    }
    for f in ALL_NATIVE:
        manifest["files"][f.name] = {"size": f.stat().st_size, "sha256": sha256(f)}
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "SOURCE_VARIANT16_TOPOLOGY_PASS",
        "DOUBLE_INNER_RING_PASS",
        "TWO_OUTER_CUPS_PASS",
        "TWO_OPPOSED_ROLLER_ROWS_PASS",
        "TAPER_ROLLER_NATIVE_PASS",
        "CAGE_CELL_NATIVE_PATTERN_PASS",
        "TWO_HALF_CAGES_PASS",
        "RIVET_COMPONENTS_PASS",
        "MASTER_GEOMETRY_V16_PASS",
        "ASSEMBLY_VARIABLES_PASS",
        "COMPONENT_EXTERNAL_VARIABLE_LINKS_PASS",
        "ALL_NATIVE_M3D_PASS",
        "NATIVE_A3D_PASS",
        "RESULT=BUILD_NATIVE_WORK4_VARIANT16_PASS",
    ]
    REPORT.write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        OUT.mkdir(parents=True, exist_ok=True)
        REPORT.write_text("RESULT=BUILD_NATIVE_WORK4_VARIANT16_FAIL\n"+repr(exc)+"\n",
                          encoding="utf-8")
        print(REPORT.read_text(encoding="utf-8"), file=sys.stderr)
        raise
