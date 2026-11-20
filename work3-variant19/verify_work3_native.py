# -*- coding: utf-8 -*-
"""Strict Work 3 acceptance: model mutation -> CDW rebuild -> nominal restore."""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import math
import sys
import zipfile

import pythoncom
from win32com.client import Dispatch, gencache

HERE = Path(__file__).resolve().parent
INPUT = HERE / "input"
OUT = HERE / "native"
CUTTER = INPUT / "Work2_V19_FormCutter.m3d"
CDW = OUT / "Work3_V19_FormCutter.cdw"
REPORT = OUT / "verification.txt"
MANIFEST = OUT / "work3-manifest.json"
SOURCE = OUT / "source-work2.json"

KOMPAS6_CONSTANTS = "{75C9F5D0-B5B8-4526-8681-9903C567D2ED}"
KOMPAS6_API5 = "{0422828C-F174-495E-AC5D-D31014DBBE87}"
KOMPAS6_API7 = "{69AC2981-37C0-4379-84FD-5DD2F3C0A520}"


def require(value, message):
    if not value:
        raise RuntimeError(message)
    return value


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def get_kompas5():
    api5 = gencache.EnsureModule(KOMPAS6_API5, 0, 1, 0)
    raw = Dispatch("Kompas.Application.5")
    return api5.KompasObject(
        raw._oleobj_.QueryInterface(api5.KompasObject.CLSID, pythoncom.IID_IDispatch)
    )


def native_file(path):
    require(path.exists() and path.stat().st_size > 1024, f"{path.name}: missing/small")
    require(zipfile.is_zipfile(path), f"{path.name}: not native KOMPAS container")
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        require("Contents" in names and "FileInfo" in names,
                f"{path.name}: Contents/FileInfo missing")


def open_drawing(kompas, path):
    doc = require(kompas.Document2D(), "Document2D")
    require(doc.ksOpenDocument(str(path), False), f"Open {path.name}")
    require(doc.ksRebuildDocument(), f"Rebuild {path.name}")
    return doc


def view_gabarit(kompas, const, doc, number=1):
    ref = require(doc.ksGetViewReference(number), f"View {number} reference")
    rect = require(kompas.GetParamStruct(const.ko_RectParam), "RectParam")
    require(rect.Init(), "RectParam.Init")
    require(doc.ksGetObjGabaritRect(ref, rect), f"Get gabarit view {number}")
    vals = (float(rect.x1), float(rect.y1), float(rect.x2), float(rect.y2))
    require(all(math.isfinite(v) for v in vals), f"Non-finite gabarit: {vals}")
    require(vals[2] > vals[0] and vals[3] > vals[1], f"Invalid gabarit: {vals}")
    return vals


def close2d(doc):
    try:
        doc.ksCloseDocument()
    except Exception:
        pass


def create_temp_mutation(kompas, const):
    model = require(kompas.Document3D(), "Document3D mutation")
    require(model.Open(str(CUTTER), False), "Open accepted cutter for mutation")
    require(model.RebuildDocument(), "Cutter rebuild before mutation")
    part = require(model.GetPart(const.pTop_Part), "Top part")
    plane = require(part.GetDefaultEntity(const.o3d_planeXOY), "XOY plane")

    sketch = require(part.NewEntity(const.o3d_sketch), "Mutation sketch")
    try:
        sketch.name = "WORK3_TEMP_ASSOCIATIVITY_PROBE"
    except Exception:
        pass
    skdef = require(sketch.GetDefinition(), "Mutation sketch definition")
    require(skdef.SetPlane(plane), "Mutation SetPlane")
    require(sketch.Create(), "Mutation sketch Create")
    ed = require(skdef.BeginEdit(), "Mutation BeginEdit")

    # A thin annular rib at the left end. It overlaps the existing cutter body
    # (nominal outer radius 90.5) and deliberately extends to radius 97 mm.
    pts = [(-89.0, 88.0), (-84.0, 88.0), (-84.0, 97.0), (-89.0, 97.0)]
    for a, b in zip(pts, pts[1:] + pts[:1]):
        require(ed.ksLineSeg(a[0], a[1], b[0], b[1], const.ksCSNormal),
                f"Mutation segment {a}->{b}")
    require(ed.ksLineSeg(-94.0, 0.0, -79.0, 0.0, const.ksCSAxis),
            "Mutation revolve axis")
    ended = skdef.EndEdit()
    if ended is False:
        raise RuntimeError("Mutation EndEdit returned False")

    feat = require(part.NewEntity(const.o3d_baseRotated), "Mutation baseRotated")
    try:
        feat.name = "WORK3_TEMP_ASSOCIATIVITY_PROBE_RING"
    except Exception:
        pass
    fd = require(feat.GetDefinition(), "Mutation revolve definition")
    fd.directionType = const.dtNormal
    require(fd.SetSideParam(True, 360.0), "Mutation SetSideParam")
    require(fd.SetSketch(sketch), "Mutation SetSketch")
    require(feat.Create(), "Mutation feature Create")
    part.Update()
    require(model.RebuildDocument(), "Cutter rebuild after mutation")
    require(model.Save(), "Save mutated cutter")
    mutated_mass = float(part.GetMass())
    try:
        model.close()
    except Exception:
        pass
    return mutated_mass


def verify_api7_structure():
    api7 = gencache.EnsureModule(KOMPAS6_API7, 0, 1, 0)
    app = Dispatch("KOMPAS.Application.7")
    app.Visible = True
    doc = require(app.Documents.Open(str(CDW), False, False), "API7 reopen final CDW")
    views = require(doc.ViewsAndLayersManager.Views, "Views")
    user_views = []
    for i in range(int(views.Count)):
        try:
            v = views.View(i)
            if int(v.Number) > 0:
                user_views.append(v)
        except Exception:
            continue
    require(len(user_views) >= 2, f"Only {len(user_views)} user views")
    user_views.sort(key=lambda v: int(v.Number))
    main, additional = user_views[0], user_views[1]

    linked = []
    for v in (main, additional):
        assoc = api7.IAssociationView(
            v._oleobj_.QueryInterface(api7.IAssociationView.CLSID, pythoncom.IID_IDispatch)
        )
        src = str(assoc.GetSourceFileName())
        require(Path(src).name.lower() == CUTTER.name.lower(),
                f"Associative view source mismatch: {src}")
        linked.append(src)

    cut = api7.ICutViewParam(
        main._oleobj_.QueryInterface(api7.ICutViewParam.CLSID, pythoncom.IID_IDispatch)
    )
    ncuts = int(cut.GetCutsCount())
    require(ncuts >= 1, "No local section persisted")
    require(any(bool(cut.IsLocalCut(i)) for i in range(ncuts)),
            "Cut exists but none is local")

    # The drawing must still be writable and rebuildable after disk reopen.
    try:
        doc.Rebuild()
    except Exception:
        pass
    require(doc.Save(), "Final API7 CDW save")
    try:
        doc.Close(0)
    except Exception:
        pass
    return linked, ncuts


def near_gabarit(a, b, tol=0.05):
    return all(abs(x-y) <= tol for x, y in zip(a, b))


def main():
    pythoncom.CoInitialize()
    OUT.mkdir(parents=True, exist_ok=True)
    native_file(CUTTER)
    native_file(CDW)
    require(MANIFEST.exists(), "Work 3 manifest missing")
    require(SOURCE.exists(), "Work 2 source gate manifest missing")

    const = gencache.EnsureModule(KOMPAS6_CONSTANTS, 0, 1, 0).constants
    kompas = get_kompas5()
    source_info = json.loads(SOURCE.read_text(encoding="utf-8"))
    original = CUTTER.read_bytes()
    original_sha = sha256_bytes(original)
    require(source_info["files"][CUTTER.name] == original_sha,
            "Input cutter SHA no longer matches accepted Work 2")

    d0 = open_drawing(kompas, CDW)
    baseline = view_gabarit(kompas, const, d0, 1)
    require(d0.ksSaveDocument(str(CDW)), "Baseline CDW save")
    close2d(d0)

    mutated_mass = create_temp_mutation(kompas, const)
    mutated_sha = sha256(CUTTER)
    require(mutated_sha != original_sha, "Model mutation did not change cutter SHA")

    dm = open_drawing(kompas, CDW)
    mutated = view_gabarit(kompas, const, dm, 1)
    require(dm.ksSaveDocument(str(CDW)), "Mutated-state CDW save")
    close2d(dm)

    baseline_w = baseline[2] - baseline[0]
    baseline_h = baseline[3] - baseline[1]
    mutated_w = mutated[2] - mutated[0]
    mutated_h = mutated[3] - mutated[1]
    physical_delta = max(abs(mutated_w-baseline_w), abs(mutated_h-baseline_h))
    require(physical_delta > 1.0,
            f"Associative CDW gabarit did not react physically: delta={physical_delta}")

    # Restore the accepted Work 2 model byte-for-byte, not by reverse editing.
    CUTTER.write_bytes(original)
    require(sha256(CUTTER) == original_sha, "Byte-exact model SHA restore failed")
    native_file(CUTTER)

    # Prove restored model itself still opens and rebuilds.
    m2 = require(kompas.Document3D(), "Document3D restored model")
    require(m2.Open(str(CUTTER), False), "Reopen restored cutter")
    require(m2.RebuildDocument(), "Rebuild restored cutter")
    try:
        m2.close()
    except Exception:
        pass

    dr = open_drawing(kompas, CDW)
    restored = view_gabarit(kompas, const, dr, 1)
    require(near_gabarit(restored, baseline),
            f"CDW did not return to nominal gabarit: baseline={baseline}, restored={restored}")
    require(dr.ksSaveDocument(str(CDW)), "Final nominal CDW save")
    close2d(dr)

    # One more independent disk reopen after nominal restore.
    df = open_drawing(kompas, CDW)
    final_gab = view_gabarit(kompas, const, df, 1)
    require(near_gabarit(final_gab, baseline),
            f"Final reopen gabarit drift: {final_gab}")
    close2d(df)

    links, ncuts = verify_api7_structure()
    native_file(CDW)
    require(sha256(CUTTER) == original_sha, "Source model changed after final verification")

    lines = [
        "WORK2_ACCEPTED_INPUT_PASS",
        "CDW_REOPEN_PASS",
        "MAIN_ASSOCIATIVE_VIEW_PASS",
        "ADDITIONAL_ASSOCIATIVE_VIEW_PASS",
        "LOCAL_SECTION_REOPEN_PASS",
        f"ASSOCIATIVE_SOURCE_LINKS={links!r}",
        f"LOCAL_CUT_COUNT={ncuts}",
        f"MODEL_SHA_BASELINE={original_sha}",
        f"MODEL_SHA_MUTATED={mutated_sha}",
        f"MODEL_MUTATED_MASS={mutated_mass:.12f}",
        f"CDW_GABARIT_BASELINE={baseline!r}",
        f"CDW_GABARIT_MUTATED={mutated!r}",
        f"CDW_GABARIT_PHYSICAL_DELTA={physical_delta:.9f}",
        f"CDW_GABARIT_RESTORED={restored!r}",
        f"CDW_GABARIT_FINAL_REOPEN={final_gab!r}",
        "MODEL_MUTATION_PASS",
        "CDW_REBUILD_PHYSICAL_CHANGE_PASS",
        "MODEL_NOMINAL_SHA_RESTORE_PASS",
        "CDW_REBUILD_NOMINAL_RESTORE_PASS",
        "FINAL_NOMINAL_REOPEN_PASS",
        f"SHA256 {CDW.name} {sha256(CDW)}",
        f"SHA256 {CUTTER.name} {sha256(CUTTER)}",
        "RESULT=PASS_NATIVE_WORK3_VARIANT19_ASSOCIATIVE_REBUILD",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        OUT.mkdir(parents=True, exist_ok=True)
        # Best-effort safety: never intentionally leave the accepted source mutated.
        try:
            src = json.loads(SOURCE.read_text(encoding="utf-8"))
            expected = src["files"][CUTTER.name]
            if CUTTER.exists() and sha256(CUTTER) != expected:
                print("WARNING=SOURCE_MODEL_SHA_NOT_NOMINAL_AFTER_FAILURE", file=sys.stderr)
        except Exception:
            pass
        REPORT.write_text("RESULT=FAIL_NATIVE_WORK3_VARIANT19\n" + repr(exc) + "\n",
                          encoding="utf-8")
        print(REPORT.read_text(encoding="utf-8"), file=sys.stderr)
        raise
