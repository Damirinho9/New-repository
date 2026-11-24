# -*- coding: utf-8 -*-
"""Prove native KOMPAS parametric mutation before Work 4 is allowed to build."""
from __future__ import annotations

from pathlib import Path
import hashlib
import math
import sys

import pythoncom

from work4_common import *

HERE = Path(__file__).resolve().parent
DETAIL = HERE / "_runtime_parametric_probe.m3d"
ASM = HERE / "_runtime_parametric_probe.a3d"
REPORT = HERE / "runtime-parametric-proof.txt"


def mass(part):
    m = float(part.GetMass())
    require(math.isfinite(m) and m > 0, f"Invalid mass {m}")
    return m


def one_component(doc, filename):
    coll = require(doc.PartCollection(True), "PartCollection")
    found = []
    for i in list(range(int(coll.GetCount()))) + list(range(1, int(coll.GetCount())+1)):
        try:
            p = coll.GetByIndex(i)
        except Exception:
            p = None
        if p and Path(part_filename(p)).name.lower() == filename.lower() and all(p is not x for x in found):
            found.append(p)
    require(found, f"Component {filename} not found")
    return found[0]


def main():
    pythoncom.CoInitialize()
    const = constants()
    kompas = get_kompas5()
    for p in (DETAIL, ASM, REPORT):
        p.unlink(missing_ok=True)

    # Detail: W must control a real extrusion after disk reopen.
    doc, part = create_part_doc(kompas, const, DETAIL, "PARAMETRIC_PROBE")
    add_user_var(part, "W", 10.0, "Probe external width", True)
    sk = circle_sketch(part, const, 20.0, 0.0, 0.0, "PROBE_PROFILE")
    ext = create_extrusion(part, const, sk, 10.0, "PROBE_EXTRUSION")
    bound = bind_feature_var_by_value(part, ext, 10.0, "W")
    require(doc.RebuildDocument(), "Probe initial rebuild")
    m10 = mass(part)
    require(doc.SaveAs(str(DETAIL)), "Probe detail SaveAs")
    close_doc(doc)
    native_file(DETAIL)

    d2 = require(kompas.Document3D(), "Probe reopen Document3D")
    require(d2.Open(str(DETAIL), False), "Probe detail reopen")
    p2 = require(d2.GetPart(const.pTop_Part), "Probe top part")
    set_var_expression(get_var(p2, "W"), "14")
    require(p2.RebuildModel(), "Probe detail RebuildModel W=14")
    require(d2.RebuildDocument(), "Probe detail RebuildDocument W=14")
    m14 = mass(p2)
    require(abs(m14-m10) > 1e-5, f"Detail parametric mass did not change: {m10} -> {m14}")
    set_var_expression(get_var(p2, "W"), "10")
    require(p2.RebuildModel(), "Probe detail restore RebuildModel")
    require(d2.RebuildDocument(), "Probe detail restore RebuildDocument")
    m10r = mass(p2)
    require(abs(m10r-m10) <= max(1e-6, m10*1e-6), "Detail mass did not restore")
    require(d2.Save(), "Probe detail save nominal")
    close_doc(d2)
    source_sha = sha256(DETAIL)

    # Assembly: top-level T controls inserted component external variable W.
    a = require(kompas.Document3D(), "Probe assembly Document3D")
    require(a.Create(False, False), "Probe assembly create")
    require(a.SaveAs(str(ASM)), "Probe assembly SaveAs")
    atop = require(a.GetPart(const.pTop_Part), "Probe assembly top")
    add_user_var(atop, "T", 20.0, "Probe assembly control", True)
    require(a.Save(), "Probe assembly variable save")
    close_doc(a)

    app7 = get_kompas7()
    ad7 = require(app7.Documents.Open(str(ASM), False, False), "Probe API7 assembly open")
    c7 = require(ad7.TopPart.Parts.AddFromFile(str(DETAIL), True, False), "Probe AddFromFile")
    try:
        c7.Name = "PARAMETRIC_COMPONENT"
    except Exception:
        pass
    require(ad7.Save(), "Probe API7 assembly save")
    try:
        ad7.Close(0)
    except Exception:
        pass

    a2 = require(kompas.Document3D(), "Probe assembly reopen")
    require(a2.Open(str(ASM), False), "Probe assembly reopen failed")
    require(a2.RebuildDocument(), "Probe assembly initial rebuild")
    at2 = require(a2.GetPart(const.pTop_Part), "Probe reopened top")
    comp = one_component(a2, DETAIL.name)
    set_var_expression(get_var(comp, "W"), "T/2")
    require(comp.RebuildModel(), "Probe component link W=T/2")
    require(a2.RebuildDocument(), "Probe assembly link rebuild")
    ma20 = mass(comp)

    set_var_expression(get_var(at2, "T"), "28")
    require(at2.RebuildModel(), "Probe assembly T=28 top rebuild")
    require(a2.RebuildDocument(), "Probe assembly T=28 document rebuild")
    ma28 = mass(comp)
    require(abs(ma28-ma20) > 1e-5, f"Assembly-scoped external variable did not change geometry: {ma20}->{ma28}")
    require(abs(component_width := var_value(get_var(comp, "W")) - 14.0) <= 1e-6,
            f"Component W did not evaluate to T/2: delta={component_width}")
    require(a2.Save(), "Probe assembly changed save")
    close_doc(a2)

    a3 = require(kompas.Document3D(), "Probe changed reopen")
    require(a3.Open(str(ASM), False), "Probe changed assembly reopen")
    require(a3.RebuildDocument(), "Probe changed assembly rebuild")
    at3 = require(a3.GetPart(const.pTop_Part), "Probe changed top")
    comp3 = one_component(a3, DETAIL.name)
    require(abs(var_value(get_var(at3, "T"))-28.0) <= 1e-6, "Probe T=28 did not persist")
    require(abs(mass(comp3)-ma28) <= max(1e-6,ma28*1e-6), "Probe changed mass did not persist")

    set_var_expression(get_var(at3, "T"), "20")
    require(at3.RebuildModel(), "Probe assembly restore T=20")
    require(a3.RebuildDocument(), "Probe assembly restore document")
    ma20r = mass(comp3)
    require(abs(ma20r-ma20) <= max(1e-6,ma20*1e-6), "Probe assembly mass did not restore")
    require(a3.Save(), "Probe assembly nominal save")
    close_doc(a3)

    require(sha256(DETAIL) == source_sha, "Assembly override mutated source M3D")
    native_file(DETAIL)
    native_file(ASM)

    lines = [
        f"FEATURE_BOUND_VARIABLES={bound!r}",
        f"DETAIL_MASS_W10={m10:.12f}",
        f"DETAIL_MASS_W14={m14:.12f}",
        "DETAIL_EXTERNAL_VARIABLE_REBUILD_PASS",
        "DETAIL_SAVE_CLOSE_REOPEN_PASS",
        f"ASSEMBLY_COMPONENT_MASS_T20={ma20:.12f}",
        f"ASSEMBLY_COMPONENT_MASS_T28={ma28:.12f}",
        "ASSEMBLY_EXTERNAL_VARIABLE_LINK_PASS",
        "ASSEMBLY_TOP_VARIABLE_PHYSICAL_CHANGE_PASS",
        "ASSEMBLY_CHANGED_SAVE_CLOSE_REOPEN_PASS",
        "ASSEMBLY_NOMINAL_RESTORE_PASS",
        "SOURCE_M3D_UNCHANGED_PASS",
        "RESULT=RUNTIME_NATIVE_PARAMETRIC_MUTATION_PASS",
    ]
    REPORT.write_text("\n".join(lines)+"\n", encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        REPORT.write_text("RESULT=RUNTIME_NATIVE_PARAMETRIC_MUTATION_FAIL\n"+repr(exc)+"\n",
                          encoding="utf-8")
        print(REPORT.read_text(encoding="utf-8"), file=sys.stderr)
        raise
