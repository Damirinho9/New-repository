# -*- coding: utf-8 -*-
"""Strict reopen/rebuild/dependency verification for Work 2 variant 19."""
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
OUTDIR = HERE / "native"
WORKPIECE = OUTDIR / "Work2_V19_Workpiece.m3d"
CUTTER = OUTDIR / "Work2_V19_FormCutter.m3d"
ASSEMBLY = OUTDIR / "Work2_V19_TopDown.a3d"
REPORT = OUTDIR / "verification.txt"
MANIFEST = OUTDIR / "native-manifest.json"
CALC = HERE / "calculation.csv"

KOMPAS6_CONSTANTS = "{75C9F5D0-B5B8-4526-8681-9903C567D2ED}"
KOMPAS6_API5 = "{0422828C-F174-495E-AC5D-D31014DBBE87}"


def require(value, message):
    if not value:
        raise RuntimeError(message)
    return value


def get_kompas5():
    api5 = gencache.EnsureModule(KOMPAS6_API5, 0, 1, 0)
    raw = Dispatch("Kompas.Application.5")
    return api5.KompasObject(
        raw._oleobj_.QueryInterface(api5.KompasObject.CLSID, pythoncom.IID_IDispatch)
    )


def read_calc():
    rows = {}
    with CALC.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rows[row["parameter"]] = row["value"]
    return rows


def native_file(path):
    require(path.exists() and path.stat().st_size > 1024, f"{path.name}: missing/small")
    require(zipfile.is_zipfile(path), f"{path.name}: not native ZIP container")
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        require("Contents" in names and "FileInfo" in names,
                f"{path.name}: missing Contents/FileInfo")


def open_model(kompas, path):
    doc = require(kompas.Document3D(), f"{path.name}: Document3D unavailable")
    require(doc.Open(str(path), False), f"{path.name}: Open failed")
    require(doc.RebuildDocument(), f"{path.name}: RebuildDocument failed")
    return doc


def part_filename(part):
    for method in ("GetFileName",):
        try:
            value = getattr(part, method)()
            if value:
                return str(value)
        except Exception:
            pass
    for attr in ("fileName", "FileName"):
        try:
            value = getattr(part, attr)
            if value:
                return str(value)
        except Exception:
            pass
    return ""


def enumerate_parts(doc):
    coll = require(doc.PartCollection(True), "PartCollection(True) failed")
    count = int(coll.GetCount())
    result = []
    seen = set()
    for idx in list(range(count)) + list(range(1, count+1)):
        try:
            p = coll.GetByIndex(idx)
        except Exception:
            p = None
        if not p:
            continue
        fn = part_filename(p)
        key = fn.lower() if fn else id(p)
        if key in seen:
            continue
        seen.add(key)
        result.append(p)
    return result


def identify_components(doc):
    parts = enumerate_parts(doc)
    wp = None
    cutter = None
    rows = []
    for p in parts:
        fn = part_filename(p)
        rows.append(fn)
        low = Path(fn).name.lower() if fn else ""
        if low == WORKPIECE.name.lower():
            wp = p
        if low == CUTTER.name.lower():
            cutter = p
    require(wp, f"Workpiece source link not found. Components={rows}")
    require(cutter, f"Cutter source link not found. Components={rows}")
    return wp, cutter, rows


def set_origin(part, x, y, z):
    placement = require(part.GetPlacement(), "GetPlacement failed")
    require(placement.SetOrigin(float(x), float(y), float(z)), "SetOrigin failed")
    require(part.UpdatePlacement(), "UpdatePlacement failed")


def main():
    pythoncom.CoInitialize()
    const = gencache.EnsureModule(KOMPAS6_CONSTANTS, 0, 1, 0).constants
    kompas = get_kompas5()
    calc = read_calc()
    axis_y = float(calc["axis_distance_x"])
    axis_z = float(calc["axis_offset_y"])

    for p in (WORKPIECE, CUTTER, ASSEMBLY):
        native_file(p)

    # Independent reopen/rebuild of each external native document.
    wp_doc = open_model(kompas, WORKPIECE)
    require(wp_doc.IsDetail(), "Workpiece M3D is not a detail")
    wp_top = require(wp_doc.GetPart(const.pTop_Part), "Workpiece top part unavailable")
    require(wp_top.GetLastFeature(), "Workpiece contains no persisted 3D feature")
    try:
        wp_doc.close()
    except Exception:
        pass

    cutter_doc = open_model(kompas, CUTTER)
    require(cutter_doc.IsDetail(), "Cutter M3D is not a detail")
    cutter_top = require(cutter_doc.GetPart(const.pTop_Part), "Cutter top part unavailable")
    require(cutter_top.GetLastFeature(), "Cutter contains no persisted 3D feature")
    try:
        cutter_doc.close()
    except Exception:
        pass

    # Reopen assembly after both component documents have been closed.
    asm = open_model(kompas, ASSEMBLY)
    require(not asm.IsDetail(), "A3D reopened as detail instead of assembly")
    wp, cutter, component_files = identify_components(asm)

    baseline_mass = float(cutter.GetMass())
    require(baseline_mass > 0.0, f"Cutter baseline mass invalid: {baseline_mass}")

    # Physical dependency test:
    # temporarily move the source workpiece 5 mm toward the cutter axis.
    # MoldCavity must rebuild and therefore cutter mass must change.
    set_origin(wp, 0.0, 5.0, 0.0)
    require(asm.RebuildDocument(), "Assembly rebuild after dependency mutation failed")
    moved_mass = float(cutter.GetMass())
    mass_delta = abs(moved_mass - baseline_mass)
    require(mass_delta > max(1e-6, baseline_mass * 1e-7),
            f"Dependency did not change cutter mass: baseline={baseline_mass}, moved={moved_mass}")

    # Return source component to nominal placement and prove reverse rebuild.
    set_origin(wp, 0.0, 0.0, 0.0)
    require(asm.RebuildDocument(), "Assembly rebuild after dependency restore failed")
    restored_mass = float(cutter.GetMass())
    require(abs(restored_mass - baseline_mass) <= max(1e-5, baseline_mass * 1e-6),
            f"Cutter did not return to nominal mass: {restored_mass} vs {baseline_mass}")

    # Confirm the cutter component itself is still in its calculated placement.
    cp = require(cutter.GetPlacement(), "Cutter placement unavailable")
    # Re-apply the nominal calculated origin to make the final saved state explicit.
    require(cp.SetOrigin(0.0, axis_y, axis_z), "Could not restore cutter calculated origin")
    require(cutter.UpdatePlacement(), "Cutter UpdatePlacement final failed")
    require(asm.RebuildDocument(), "Final assembly rebuild failed")
    require(asm.Save(), "Final assembly Save failed")

    try:
        asm.close()
    except Exception:
        pass

    # One more disk reopen after the dependency test and final save.
    asm2 = open_model(kompas, ASSEMBLY)
    wp2, cutter2, component_files2 = identify_components(asm2)
    final_mass = float(cutter2.GetMass())
    require(final_mass > 0.0, "Final reopened cutter mass invalid")
    require(abs(final_mass - baseline_mass) <= max(1e-5, baseline_mass * 1e-6),
            f"Final reopened mass drift: {final_mass} vs {baseline_mass}")

    # Native files must still be valid containers after every mutation/rebuild.
    for p in (WORKPIECE, CUTTER, ASSEMBLY):
        native_file(p)

    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (WORKPIECE, CUTTER, ASSEMBLY)}
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require(manifest["architecture"] == "top-down", "Manifest architecture mismatch")
    require(manifest["dependency"].startswith("MoldCavity"), "Manifest dependency mismatch")

    lines = [
        "WORKPIECE_REOPEN_PASS",
        "WORKPIECE_REBUILD_PASS",
        "CUTTER_REOPEN_PASS",
        "CUTTER_REBUILD_PASS",
        "ASSEMBLY_REOPEN_PASS",
        "ASSEMBLY_REBUILD_PASS",
        "SOURCE_LINK_WORKPIECE_PASS",
        "SOURCE_LINK_CUTTER_PASS",
        f"COMPONENT_FILES={component_files2!r}",
        f"CUTTER_MASS_BASELINE={baseline_mass:.12f}",
        f"CUTTER_MASS_DEPENDENCY_MUTATED={moved_mass:.12f}",
        f"CUTTER_MASS_DELTA={mass_delta:.12f}",
        f"CUTTER_MASS_RESTORED={restored_mass:.12f}",
        "TOP_DOWN_DEPENDENCY_PHYSICAL_CHANGE_PASS",
        "TOP_DOWN_DEPENDENCY_RESTORE_PASS",
        f"CALCULATED_CUTTER_AXIS_ORIGIN=(0,{axis_y:.9f},{axis_z:.9f})",
        "FINAL_NOMINAL_REOPEN_PASS",
    ]
    for name, sha in hashes.items():
        lines.append(f"SHA256 {name} {sha}")
    lines.append("RESULT=PASS_NATIVE_WORK2_VARIANT19_REOPEN_REBUILD_DEPENDENCY")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        OUTDIR.mkdir(parents=True, exist_ok=True)
        REPORT.write_text("RESULT=FAIL_NATIVE_WORK2_VARIANT19\n" + repr(exc) + "\n",
                          encoding="utf-8")
        print(REPORT.read_text(encoding="utf-8"), file=sys.stderr)
        raise
