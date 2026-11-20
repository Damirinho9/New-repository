# -*- coding: utf-8 -*-
"""Work 2, variant 19: native KOMPAS .m3d + .a3d, built top-down.

The assembly is created first. Both external parts are created *in the assembly*
with CreatePartInAssembly. The cutter then receives an in-place MoldCavity
operation that references the workpiece component, creating a real native
cross-component dependency.

All nominal dimensions are read from calculation.csv, which is the independent
calculation source of truth produced before CAD.
"""
from __future__ import annotations

from pathlib import Path
import csv
import hashlib
import json
import math
import sys
import zipfile

import pythoncom
from win32com.client import Dispatch, gencache

HERE = Path(__file__).resolve().parent
CALC = HERE / "calculation.csv"
OUTDIR = HERE / "native"
WORKPIECE = OUTDIR / "Work2_V19_Workpiece.m3d"
CUTTER = OUTDIR / "Work2_V19_FormCutter.m3d"
ASSEMBLY = OUTDIR / "Work2_V19_TopDown.a3d"
REPORT = OUTDIR / "build-report.txt"
MANIFEST = OUTDIR / "native-manifest.json"

KOMPAS6_CONSTANTS = "{75C9F5D0-B5B8-4526-8681-9903C567D2ED}"
KOMPAS6_API5 = "{0422828C-F174-495E-AC5D-D31014DBBE87}"

STEEL60_DENSITY_G_CM3 = 7.85
CUTTER_STEEL_DENSITY_G_CM3 = 8.30


def require(value, message):
    if not value:
        raise RuntimeError(message)
    return value


def read_calc():
    rows = {}
    with CALC.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rows[row["parameter"]] = row["value"]
    def num(name):
        return float(rows[name])
    return rows, num


def get_kompas5():
    api5 = gencache.EnsureModule(KOMPAS6_API5, 0, 1, 0)
    raw = Dispatch("Kompas.Application.5")
    return api5.KompasObject(
        raw._oleobj_.QueryInterface(api5.KompasObject.CLSID, pythoncom.IID_IDispatch)
    )


def set_object_name(obj, name):
    for attr in ("name", "Name"):
        try:
            setattr(obj, attr, name)
            return
        except Exception:
            pass


def create_sketch(part, const, plane, name):
    sketch = require(part.NewEntity(const.o3d_sketch), f"{name}: NewEntity(sketch)")
    set_object_name(sketch, name)
    definition = require(sketch.GetDefinition(), f"{name}: GetDefinition")
    require(definition.SetPlane(plane), f"{name}: SetPlane")
    require(sketch.Create(), f"{name}: Create")
    editor = require(definition.BeginEdit(), f"{name}: BeginEdit")
    return sketch, definition, editor


def end_sketch(definition):
    result = definition.EndEdit()
    if result is False:
        raise RuntimeError("Sketch EndEdit returned False")


def add_axis(editor, const, x1, x2):
    return require(editor.ksLineSeg(x1, 0.0, x2, 0.0, const.ksCSAxis),
                   "Could not create revolve axis")


def polyline(editor, const, points):
    refs = []
    for a, b in zip(points, points[1:] + points[:1]):
        refs.append(require(editor.ksLineSeg(a[0], a[1], b[0], b[1], const.ksCSNormal),
                            f"ksLineSeg failed: {a}->{b}"))
    return refs


def circle_arc_midpoint(p1, p2, radius, prefer_upper=True):
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2-x1, y2-y1
    chord = math.hypot(dx, dy)
    if chord >= 2*radius:
        raise RuntimeError("R is too small for the requested profile endpoints")
    mx, my = (x1+x2)/2.0, (y1+y2)/2.0
    h = math.sqrt(radius*radius - (chord/2.0)**2)
    nx, ny = -dy/chord, dx/chord
    centers = [(mx+h*nx, my+h*ny), (mx-h*nx, my-h*ny)]
    candidates = []
    for cx, cy in centers:
        a1 = math.atan2(y1-cy, x1-cx)
        a2 = math.atan2(y2-cy, x2-cx)
        delta = (a2-a1 + math.pi) % (2*math.pi) - math.pi
        am = a1 + delta/2.0
        pm = (cx + radius*math.cos(am), cy + radius*math.sin(am))
        candidates.append(pm)
    return max(candidates, key=lambda p: p[1]) if prefer_upper else min(candidates, key=lambda p: p[1])


def create_base_rotated(part, const, sketch, name):
    entity = require(part.NewEntity(const.o3d_baseRotated), f"{name}: NewEntity(baseRotated)")
    set_object_name(entity, name)
    definition = require(entity.GetDefinition(), f"{name}: GetDefinition")
    definition.directionType = const.dtNormal
    require(definition.SetSideParam(True, 360.0), f"{name}: SetSideParam")
    require(definition.SetSketch(sketch), f"{name}: SetSketch")
    require(entity.Create(), f"{name}: Create")
    return entity


def create_cut_extrusion(part, const, sketch, depth, name):
    entity = require(part.NewEntity(const.o3d_cutExtrusion), f"{name}: NewEntity(cutExtrusion)")
    set_object_name(entity, name)
    definition = require(entity.GetDefinition(), f"{name}: GetDefinition")
    definition.directionType = const.dtReverse
    require(definition.SetSketch(sketch), f"{name}: SetSketch")
    # Flange lies in negative X from the YOZ sketch plane at X=0.
    ok = definition.SetSideParam(False, const.etBlind, depth, 0.0, False)
    require(ok, f"{name}: SetSideParam")
    require(entity.Create(), f"{name}: Create")
    return entity


def build_workpiece(part, const, values):
    # Scheme 1 axisymmetric profile. The axial coordinate is [-L, 0].
    D1, D2, D3 = values["D1"], values["D2"], values["D3"]
    l1, l2, l3, l4 = values["part_l1"], values["part_l2"], values["part_l3"], values["part_l4"]
    L, R = values["L_part"], values["R_part"]
    r1, r2, r3 = D1/2.0, D2/2.0, D3/2.0

    x0 = -L
    x1 = x0 + l1
    x2 = x0 + l2
    x3 = x2 + l3
    x4 = -l4
    x5 = 0.0
    require(x0 < x1 <= x2 < x3 < x4 < x5, "Invalid axial scheme-1 dimensions")

    plane = require(part.GetDefaultEntity(const.o3d_planeXOY), "Workpiece XOY plane")
    sketch, skdef, d2 = create_sketch(part, const, plane, "WORKPIECE_PROFILE")

    # Closed contour, with one true R21 transition.
    pts_before_arc = [(x0, 0.0), (x0, r3), (x1, r3), (x2, r2), (x3, r2)]
    for a, b in zip(pts_before_arc, pts_before_arc[1:]):
        require(d2.ksLineSeg(a[0], a[1], b[0], b[1], const.ksCSNormal),
                f"Workpiece line failed {a}->{b}")

    p_arc1 = (x3, r2)
    p_arc2 = (x4, r1)
    pm = circle_arc_midpoint(p_arc1, p_arc2, R, True)
    require(d2.ksArcBy3Points(p_arc1[0], p_arc1[1], pm[0], pm[1],
                             p_arc2[0], p_arc2[1], const.ksCSNormal),
            "Workpiece R21 arc failed")

    tail = [(x4, r1), (x5, r1), (x5, 0.0), (x0, 0.0)]
    for a, b in zip(tail, tail[1:]):
        require(d2.ksLineSeg(a[0], a[1], b[0], b[1], const.ksCSNormal),
                f"Workpiece tail line failed {a}->{b}")

    add_axis(d2, const, x0-5.0, x5+5.0)
    end_sketch(skdef)
    create_base_rotated(part, const, sketch, "WORKPIECE_REVOLVE")
    require(part.SetMaterial("Сталь 60", STEEL60_DENSITY_G_CM3), "SetMaterial Steel 60")
    part.Update()
    return {
        "x": [x0, x1, x2, x3, x4, x5],
        "diameters": [D1, D2, D3],
        "R": R,
    }


def build_cutter_blank(part, const, values):
    d = values["d_adopted"]
    da = values["d_a_calc"]
    L0 = values["overall_length"]
    flange_d = values["flange_d_adopted"]
    flange_w = values["flange_width"]
    recess_d = values["mount_recess_d"]
    recess_len = values["mount_recess_length"]
    tech_d = values["tech_recess_d"]

    rin = d/2.0
    rout = da/2.0
    rflange = flange_d/2.0
    rrecess = recess_d/2.0
    rtech = tech_d/2.0

    main_right = -flange_w
    left = -L0
    recess_end = left + recess_len
    tech_start = main_right - 15.0

    require(rout > rflange > rrecess > rtech > rin, "Cutter radial dimensions are inconsistent")
    require(left < recess_end < tech_start < main_right < 0.0, "Cutter axial dimensions are inconsistent")

    plane = require(part.GetDefaultEntity(const.o3d_planeXOY), "Cutter XOY plane")
    sketch, skdef, d2 = create_sketch(part, const, plane, "CUTTER_MASTER_PROFILE")

    # One closed annular profile contains the bore, left mounting recess,
    # technological relief, main body and the 100x5 flange.
    profile = [
        (left, rrecess),
        (recess_end, rrecess),
        (recess_end, rin),
        (tech_start, rin),
        (tech_start, rtech),
        (main_right, rtech),
        (main_right, rin),
        (0.0, rin),
        (0.0, rflange),
        (main_right, rflange),
        (main_right, rout),
        (left, rout),
    ]
    polyline(d2, const, profile)
    add_axis(d2, const, left-5.0, 5.0)
    end_sketch(skdef)
    create_base_rotated(part, const, sketch, "CUTTER_BLANK_REVOLVE")

    require(part.SetMaterial("Быстрорежущая сталь", CUTTER_STEEL_DENSITY_G_CM3),
            "SetMaterial cutter")
    part.Update()

    # One radial V groove on the flange face at X=0.
    face_plane = require(part.GetDefaultEntity(const.o3d_planeYOZ), "Cutter YOZ plane")
    groove_sketch, groove_def, gd2 = create_sketch(part, const, face_plane, "RIFFLING_SEED")
    groove_depth_radial = values["rifling_profile_offset_1"]
    half_width = values["rifling_profile_offset_2"]
    # 90-degree V profile, exactly from the calculation offsets.
    gp = [
        (-half_width, rflange),
        (0.0, rflange - groove_depth_radial),
        (half_width, rflange),
    ]
    polyline(gd2, const, gp)
    end_sketch(groove_def)
    groove = create_cut_extrusion(part, const, groove_sketch, 1.5, "RIFFLING_GROOVE_1")

    # 32 real radial grooves using KOMPAS circular-copy operation.
    array = require(part.NewEntity(const.o3d_circularCopy), "NewEntity(circularCopy)")
    set_object_name(array, "RIFFLING_32")
    arr_def = require(array.GetDefinition(), "CircularCopy definition")
    operations = require(arr_def.GetOperationArray(), "CircularCopy operation array")
    require(operations.Add(groove), "CircularCopy add seed groove")
    axis = require(part.GetDefaultEntity(const.o3d_axisOX), "Default OX axis")
    require(arr_def.SetAxis(axis), "CircularCopy SetAxis")
    try:
        arr_def.SetGeomArray(True)
    except Exception:
        pass
    try:
        require(arr_def.SetCopyParamAlongDir(int(values["rifling_z"]), 360.0, True, False),
                "CircularCopy SetCopyParamAlongDir")
    except Exception:
        arr_def.count2 = int(values["rifling_z"])
        arr_def.factor2 = True
    require(array.Create(), "CircularCopy.Create failed")
    return {
        "d": d,
        "da": da,
        "L0": L0,
        "flange_d": flange_d,
        "flange_w": flange_w,
        "recess_d": recess_d,
        "recess_len": recess_len,
        "tech_d": tech_d,
        "rifling_z": int(values["rifling_z"]),
    }


def position_component(part, y, z):
    placement = require(part.GetPlacement(), "GetPlacement failed")
    require(placement.SetOrigin(0.0, y, z), "Placement.SetOrigin failed")
    require(part.UpdatePlacement(), "UpdatePlacement failed")


def add_mold_cavity(cutter_part, workpiece_part, const):
    require(cutter_part.BeginEdit(), "Cutter BeginEdit for dependency failed")
    try:
        entity = require(cutter_part.NewEntity(const.o3d_MoldCavity), "NewEntity(MoldCavity)")
        set_object_name(entity, "TOP_DOWN_WORKPIECE_DEPENDENCY")
        definition = require(entity.GetDefinition(), "MoldCavity definition")
        try:
            definition.scale = 0.0
        except Exception:
            pass
        parts = require(definition.PartArray(), "MoldCavity PartArray")
        require(parts.Add(workpiece_part), "MoldCavity PartArray.Add(workpiece)")
        require(entity.Create(), "MoldCavity.Create failed")
    finally:
        require(cutter_part.EndEdit(True), "Cutter EndEdit after dependency failed")


def assert_native(path):
    require(path.exists() and path.stat().st_size > 1024, f"{path.name} missing/small")
    require(zipfile.is_zipfile(path), f"{path.name} is not a native modern KOMPAS container")


def main():
    pythoncom.CoInitialize()
    const = gencache.EnsureModule(KOMPAS6_CONSTANTS, 0, 1, 0).constants
    kompas = get_kompas5()
    rows, num = read_calc()

    values = {
        "D1": num("D1"),
        "D2": num("D2"),
        "D3": num("D3"),
        "part_l1": num("part_l1"),
        "part_l2": num("part_l2"),
        "part_l3": num("part_l3"),
        "part_l4": num("part_l4"),
        "L_part": num("L_part"),
        "R_part": num("R_part"),
        "alpha": num("alpha"),
        "gamma": num("gamma"),
        "d_adopted": num("d_adopted"),
        "d_a_calc": num("d_a_calc"),
        "e_adopted": num("e_adopted"),
        "a": num("a"),
        "axis_distance_x": num("axis_distance_x"),
        "axis_offset_y": num("axis_offset_y"),
        "flange_d_adopted": num("flange_d_adopted"),
        "flange_width": num("flange_width"),
        "mount_recess_d": num("mount_recess_d"),
        "mount_recess_length": num("mount_recess_length"),
        "tech_recess_d": num("tech_recess_d"),
        "overall_length": num("overall_length"),
        "rifling_z": num("rifling_z"),
        "rifling_profile_offset_1": num("rifling_profile_offset_1"),
        "rifling_profile_offset_2": num("rifling_profile_offset_2"),
    }

    # Calculation contract, fail before CAD if CSV drifts.
    require(values["D1"] == 80 and values["D2"] == 70 and values["D3"] == 50, "Variant diameters drift")
    require(values["d_adopted"] == 65, "Mounting bore drift")
    require(values["d_a_calc"] == 181, "Outside diameter drift")
    require(values["overall_length"] == 89, "Overall cutter length drift")
    require(int(values["rifling_z"]) == 32, "Rifling count drift")

    OUTDIR.mkdir(parents=True, exist_ok=True)
    for p in (WORKPIECE, CUTTER, ASSEMBLY, REPORT, MANIFEST):
        p.unlink(missing_ok=True)

    # TOP-DOWN: assembly exists before either part.
    asm = require(kompas.Document3D(), "Document3D() for assembly")
    require(asm.Create(False, False), "Create assembly failed")
    require(asm.SaveAs(str(ASSEMBLY)), "Initial assembly SaveAs failed")
    top = require(asm.GetPart(const.pTop_Part), "Assembly top part")
    base_plane = require(top.GetDefaultEntity(const.o3d_planeXOY), "Assembly XOY plane")

    # Part 1 is created in assembly.
    workpiece = require(asm.CreatePartInAssembly(str(WORKPIECE), base_plane),
                        "CreatePartInAssembly(workpiece) failed")
    set_object_name(workpiece, "WORKPIECE_V19")
    require(workpiece.BeginEdit(), "Workpiece BeginEdit failed")
    try:
        workpiece_meta = build_workpiece(workpiece, const, values)
    finally:
        require(workpiece.EndEdit(True), "Workpiece EndEdit failed")

    # Part 2 is also created in assembly, not standalone.
    cutter = require(asm.CreatePartInAssembly(str(CUTTER), base_plane),
                     "CreatePartInAssembly(cutter) failed")
    set_object_name(cutter, "FORM_CUTTER_V19")
    require(cutter.BeginEdit(), "Cutter BeginEdit failed")
    try:
        cutter_meta = build_cutter_blank(cutter, const, values)
    finally:
        require(cutter.EndEdit(True), "Cutter EndEdit failed")

    # Put cutter axis in the calculated transverse position. Both component
    # axes remain parallel to assembly X.
    position_component(cutter, values["axis_distance_x"], values["axis_offset_y"])

    # Real native cross-part dependency.
    add_mold_cavity(cutter, workpiece, const)

    require(asm.RebuildDocument(), "Assembly RebuildDocument failed")
    require(asm.Save(), "Assembly Save failed")

    # Saving the assembly must also have produced external component files.
    for p in (WORKPIECE, CUTTER, ASSEMBLY):
        assert_native(p)

    manifest = {
        "variant": 19,
        "architecture": "top-down",
        "assembly_first": True,
        "dependency": "MoldCavity cutter <- workpiece component",
        "workpiece": workpiece_meta,
        "cutter": cutter_meta,
        "axis_position": {
            "assembly_origin": [0.0, values["axis_distance_x"], values["axis_offset_y"]],
            "parallel_axis": "X",
        },
        "calculation_source": "calculation.csv",
        "files": {},
    }
    for p in (WORKPIECE, CUTTER, ASSEMBLY):
        manifest["files"][p.name] = {
            "size": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "ASSEMBLY_FIRST_PASS",
        "WORKPIECE_CREATE_PART_IN_ASSEMBLY_PASS",
        "CUTTER_CREATE_PART_IN_ASSEMBLY_PASS",
        "WORKPIECE_NATIVE_M3D_PASS",
        "CUTTER_NATIVE_M3D_PASS",
        "RIFFLING_32_NATIVE_PATTERN_PASS",
        "TOP_DOWN_MOLD_CAVITY_DEPENDENCY_PASS",
        "ASSEMBLY_REBUILD_PASS",
        "ASSEMBLY_NATIVE_A3D_PASS",
        "RESULT=BUILD_NATIVE_WORK2_VARIANT19_PASS",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        OUTDIR.mkdir(parents=True, exist_ok=True)
        REPORT.write_text("RESULT=BUILD_NATIVE_WORK2_VARIANT19_FAIL\n" + repr(exc) + "\n",
                          encoding="utf-8")
        print(REPORT.read_text(encoding="utf-8"), file=sys.stderr)
        raise
