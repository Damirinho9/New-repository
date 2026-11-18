# -*- coding: utf-8 -*-
"""Strict proof that the current Windows KOMPAS runtime can mutate a native 3D file.

The proof is intentionally tiny and uses the same API5/COM server that Work 2 uses:
create part -> sketch -> base extrusion -> SaveAs -> close -> reopen -> rebuild ->
confirm a persisted feature. No Work 2 build is allowed unless this script passes.
"""
from pathlib import Path
import hashlib
import sys
import zipfile

import pythoncom
from win32com.client import Dispatch, gencache

HERE = Path(__file__).resolve().parent
OUT = HERE / "_runtime_native_mutation_proof.m3d"
REPORT = HERE / "runtime-proof.txt"

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


def create_sketch(part, const, plane_type):
    plane = require(part.GetDefaultEntity(plane_type), "Default sketch plane unavailable")
    sketch = require(part.NewEntity(const.o3d_sketch), "NewEntity(o3d_sketch) failed")
    definition = require(sketch.GetDefinition(), "Sketch definition unavailable")
    require(definition.SetPlane(plane), "SetPlane failed")
    require(sketch.Create(), "Sketch.Create failed")
    editor = require(definition.BeginEdit(), "Sketch BeginEdit failed")
    return sketch, definition, editor


def main():
    pythoncom.CoInitialize()
    const = gencache.EnsureModule(KOMPAS6_CONSTANTS, 0, 1, 0).constants
    kompas = get_kompas5()

    OUT.unlink(missing_ok=True)
    REPORT.unlink(missing_ok=True)

    doc = require(kompas.Document3D(), "Document3D() returned None")
    require(doc.Create(False, True), "Could not create native 3D part document")

    part = require(doc.GetPart(const.pTop_Part), "Top part unavailable")
    sketch, sketch_def, d2 = create_sketch(part, const, const.o3d_planeXOY)
    require(d2.ksCircle(0.0, 0.0, 10.0, const.ksCSNormal), "ksCircle failed")
    sketch_def.EndEdit()

    base = require(part.NewEntity(const.o3d_baseExtrusion), "NewEntity(baseExtrusion) failed")
    base_def = require(base.GetDefinition(), "BaseExtrusion definition unavailable")
    require(base_def.SetSketch(sketch), "BaseExtrusion SetSketch failed")
    base_def.directionType = const.dtNormal
    require(base_def.SetSideParam(True, const.etBlind, 10.0, 0.0, False),
            "BaseExtrusion SetSideParam failed")
    require(base.Create(), "BaseExtrusion.Create failed")

    require(doc.RebuildDocument(), "Initial RebuildDocument failed")
    require(doc.SaveAs(str(OUT)), "SaveAs proof M3D failed")
    require(OUT.exists() and OUT.stat().st_size > 1024, "Proof M3D missing or too small")
    require(zipfile.is_zipfile(OUT), "Proof M3D is not a native modern KOMPAS container")

    try:
        doc.close()
    except Exception:
        pass

    reopened = require(kompas.Document3D(), "Second Document3D() returned None")
    require(reopened.Open(str(OUT), False), "Reopen proof M3D failed")
    require(reopened.RebuildDocument(), "Rebuild after reopen failed")
    reopened_part = require(reopened.GetPart(const.pTop_Part), "Reopened top part unavailable")
    require(reopened_part.GetLastFeature(), "Persisted 3D feature not found after reopen")

    sha = hashlib.sha256(OUT.read_bytes()).hexdigest()
    lines = [
        "RUNTIME=Windows_COM_KOMPAS",
        f"FILE={OUT.name}",
        f"SIZE={OUT.stat().st_size}",
        f"SHA256={sha}",
        "CREATE_SKETCH_PASS",
        "CREATE_BASE_EXTRUSION_PASS",
        "SAVE_AS_PASS",
        "REOPEN_PASS",
        "REBUILD_PASS",
        "PERSISTED_FEATURE_PASS",
        "RESULT=RUNTIME_NATIVE_3D_MUTATION_PASS",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        REPORT.write_text("RESULT=RUNTIME_NATIVE_3D_MUTATION_FAIL\n" + repr(exc) + "\n",
                          encoding="utf-8")
        print(REPORT.read_text(encoding="utf-8"), file=sys.stderr)
        raise
