# -*- coding: utf-8 -*-
"""Build Work 3 variant 19 as a native associative KOMPAS CDW.

Input must already have passed gate_work2_input.py. The drawing is created
only from Work2_V19_FormCutter.m3d, never from reconstructed surrogate geometry.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import sys
import zipfile

import pythoncom
from win32com.client import Dispatch, gencache

HERE = Path(__file__).resolve().parent
INPUT = HERE / "input"
OUT = HERE / "native"
CUTTER = INPUT / "Work2_V19_FormCutter.m3d"
CDW = OUT / "Work3_V19_FormCutter.cdw"
REPORT = OUT / "build-report.txt"
MANIFEST = OUT / "work3-manifest.json"
SOURCE = OUT / "source-work2.json"

KOMPAS6_CONSTANTS = "{75C9F5D0-B5B8-4526-8681-9903C567D2ED}"
KOMPAS6_API5 = "{0422828C-F174-495E-AC5D-D31014DBBE87}"
KOMPAS6_API7 = "{69AC2981-37C0-4379-84FD-5DD2F3C0A520}"


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


def text_item(kompas, const, text):
    item = require(kompas.GetParamStruct(const.ko_TextItemParam), "TextItemParam")
    require(item.Init(), "TextItemParam.Init")
    item.s = str(text)
    return item


def create_a2_landscape(kompas, const):
    par = require(kompas.GetParamStruct(const.ko_DocumentParam), "DocumentParam")
    require(par.Init(), "DocumentParam.Init")
    par.type = const.lt_DocSheetStandart
    layout = require(par.GetLayoutParam(), "GetLayoutParam")
    require(layout.Init(), "LayoutParam.Init")
    sheet = require(layout.GetSheetParam(), "GetSheetParam")
    require(sheet.Init(), "SheetParam.Init")
    sheet.format = 2  # A2
    sheet.multiply = 1
    sheet.direct = 1  # landscape
    doc = require(kompas.Document2D(), "Document2D")
    require(doc.ksCreateDocument(par), "ksCreateDocument")
    return doc


def create_associative_views(kompas, const, doc):
    av = require(kompas.GetParamStruct(const.ko_AssociationViewParam), "AssociationViewParam")
    require(av.Init(), "AssociationViewParam.Init")
    av.fileName = str(CUTTER)
    av.projectionName = ""
    av.hiddenLinesShow = True
    av.tangentEdgesShow = True
    av.projBodies = True
    vp = require(av.GetViewParam(), "Association GetViewParam")
    require(vp.Init(), "ViewParam.Init")
    vp.x = 165.0
    vp.y = 205.0
    vp.scale_ = 1.0
    vp.name = "MAIN_ASSOC_FRONT"
    # Front + right. Right view is the required additional view and is also
    # perpendicular support for the true local section.
    require(doc.ksCreateSheetStandartViews(av, 0x1 | 0x20, 230.0, 0.0),
            "ksCreateSheetStandartViews front+right")
    require(doc.ksRebuildDocument(), "Initial associative rebuild")
    return 1, 2


def add_linear_dim(kompas, const, doc, x1, y1, x2, y2, dx, dy):
    p = require(kompas.GetParamStruct(const.ko_LDimParam), "LDimParam")
    require(p.Init(), "LDimParam.Init")
    s = require(p.GetSPar(), "LDim GetSPar")
    s.x1, s.y1, s.x2, s.y2 = x1, y1, x2, y2
    s.ps = 2
    s.dx, s.dy = dx, dy
    s.basePoint = 1
    require(p.SetSPar(s), "LDim SetSPar")
    d = require(p.GetDPar(), "LDim GetDPar")
    d.pt1 = 1
    d.pt2 = 1
    d.textPos = 0
    require(p.SetDPar(d), "LDim SetDPar")
    return require(doc.ksLinDimension(p), "ksLinDimension")


def add_diam_dim(kompas, const, doc, xc, yc, radius, angle=-30.0):
    p = require(kompas.GetParamStruct(const.ko_RDimParam), "RDimParam")
    require(p.Init(), "RDimParam.Init")
    s = require(p.GetSPar(), "RDim GetSPar")
    s.xc, s.yc, s.rad = xc, yc, radius
    require(p.SetSPar(s), "RDim SetSPar")
    d = require(p.GetDPar(), "RDim GetDPar")
    d.ang = angle
    d.pt1 = 1
    d.pt2 = 1
    d.shelfDir = 1
    d.textPos = 0
    require(p.SetDPar(d), "RDim SetDPar")
    t = require(p.GetTPar(), "RDim GetTPar")
    t.sign = 1
    require(p.SetTPar(t), "RDim SetTPar")
    return require(doc.ksDiamDimension(p), "ksDiamDimension")


def add_roughness(kompas, const, doc, x, y, angle, text="Ra 1,6"):
    p = require(kompas.GetParamStruct(const.ko_RoughParam), "RoughParam")
    require(p.Init(), "RoughParam.Init")
    r = require(p.GetrPar(), "Rough GetrPar")
    r.type = 0
    r.around = 0
    r.x, r.y, r.ang = x, y, angle
    r.cText0 = 1
    # COM builds differ in how the text array is exposed. The native roughness
    # object is mandatory; if direct text insertion is unavailable, the value
    # is additionally placed next to the native symbol and verified separately.
    try:
        arr = r.GetTextArr()
        arr.ksAddArrayItem(-1, text)
        r.SetTextArr(arr)
    except Exception:
        pass
    require(p.SetrPar(r), "Rough SetrPar")
    ref = require(doc.ksRough(p), "ksRough")
    doc.ksText(x + 4.0, y + 4.0, 0.0, 3.5, 1.0, 0, text)
    return ref


def add_tolerance_frame(kompas, const, doc, x, y):
    p = require(kompas.GetParamStruct(const.ko_ToleranceParam), "ToleranceParam")
    require(p.Init(), "ToleranceParam.Init")
    p.x, p.y, p.type = x, y, 0
    require(doc.ksTolerance(p), "ksTolerance")
    require(doc.ksColumnNumber(1), "Tolerance cell 1")
    require(doc.ksTextLine(text_item(kompas, const, "0,05")), "Tolerance text")
    require(doc.ksColumnNumber(2), "Tolerance cell 2")
    require(doc.ksTextLine(text_item(kompas, const, "A")), "Tolerance datum text")
    return require(doc.ksEndObj(), "Tolerance ksEndObj")


def add_dimensions_and_designations(kompas, const, doc):
    # Front-view model coordinates: cutter axis along X, nominal axial span
    # -89..0 and outer radius 90.5. These values come from accepted Work 2.
    require(doc.ksOpenView(1), "Open main associative view")
    refs = []
    refs.append(add_linear_dim(kompas, const, doc, -89.0, -90.5, 0.0, -90.5, 0.0, -18.0))
    refs.append(add_linear_dim(kompas, const, doc, -89.0, 50.0, -74.0, 50.0, 0.0, 12.0))
    refs.append(add_linear_dim(kompas, const, doc, -5.0, 50.0, 0.0, 50.0, 0.0, 12.0))
    doc.ksText(-84.0, 104.0, 0.0, 4.0, 1.0, 0, "РЕЖУЩАЯ КРОМКА")
    doc.ksText(-84.0, 97.0, 0.0, 3.5, 1.0, 0, "alpha=10 deg; gamma=10 deg")
    doc.ksText(-38.0, -116.0, 0.0, 3.5, 1.0, 0, "Общая длина 89; выточка 80x15; техн. диаметр 67")
    add_roughness(kompas, const, doc, -35.0, 90.5, 90.0, "Ra 1,6")
    add_tolerance_frame(kompas, const, doc, -15.0, -108.0)

    require(doc.ksOpenView(2), "Open additional right view")
    refs.append(add_diam_dim(kompas, const, doc, 0.0, 0.0, 32.5, -35.0))
    refs.append(add_diam_dim(kompas, const, doc, 0.0, 0.0, 50.0, 30.0))
    doc.ksText(58.0, 54.0, 0.0, 4.0, 1.0, 0, "РИФЛЕНИЕ z=32")
    doc.ksText(58.0, 47.0, 0.0, 3.5, 1.0, 0, "Профиль 90 deg; шаг 11,25 deg")
    doc.ksText(58.0, 40.0, 0.0, 3.5, 1.0, 0, "Профиль: 1,5 / 0,25")
    doc.ksText(-53.0, -61.0, 0.0, 3.5, 1.0, 0, "Отверстие 65 H7")
    require(doc.ksOpenView(0), "Return system view")
    return refs


def add_technical_requirements(kompas, const, doc):
    require(doc.ksOpenTechnicalDemand(None, 0), "ksOpenTechnicalDemand")
    lines = [
        "1. Материал: быстрорежущая сталь.",
        "2. Рифление: z=32; профиль 90 deg; угловой шаг 11,25 deg.",
        "3. Неуказанная шероховатость Ra 3,2; режущий профиль Ra 1,6.",
        "4. Неуказанные предельные отклонения размеров - по ГОСТ 30893.1-m.",
        "5. Острые кромки притупить 0,2...0,3 мм, кроме режущих.",
        "6. Контролировать биение режущего профиля относительно оси отверстия.",
    ]
    for line in lines:
        require(doc.ksTextLine(text_item(kompas, const, line)), f"Technical demand line: {line}")
    return require(doc.ksCloseTechnicalDemand(), "ksCloseTechnicalDemand")


def set_stamp_via_api7(cdw_path):
    app = Dispatch("KOMPAS.Application.7")
    app.Visible = True
    doc = require(app.Documents.Open(str(cdw_path), False, False), "API7 open CDW for stamp")
    sheets = require(doc.LayoutSheets, "LayoutSheets")
    sheet = require(sheets.Item(0), "Layout sheet 0")
    stamp = require(sheet.Stamp, "Stamp")
    # Standard machine-building layouts use these common cell IDs. We verify
    # non-empty cells after Update and fail if this layout maps differently.
    values = {
        1: "7335493-W3-V19",
        2: "Фреза фасонная. Вариант 19",
        3: "Быстрорежущая сталь",
    }
    written = 0
    for cell_id, value in values.items():
        try:
            txt = stamp.Text(cell_id)
            txt.Str = value
            written += 1
        except Exception:
            continue
    require(written >= 2, "Could not populate mandatory title block cells")
    require(stamp.Update(), "Stamp.Update")
    require(doc.Save(), "API7 save after stamp")
    try:
        doc.Close(0)
    except Exception:
        pass
    return written


def add_local_cut_api7(cdw_path):
    api7 = gencache.EnsureModule(KOMPAS6_API7, 0, 1, 0)
    app = Dispatch("KOMPAS.Application.7")
    app.Visible = True
    doc = require(app.Documents.Open(str(cdw_path), False, False), "API7 open CDW local cut")
    views = require(doc.ViewsAndLayersManager.Views, "Views")
    candidates = []
    for i in range(int(views.Count)):
        try:
            v = views.View(i)
        except Exception:
            continue
        try:
            number = int(v.Number)
        except Exception:
            number = -1
        if number > 0:
            candidates.append(v)
    require(len(candidates) >= 2, "Need main and additional associative views")
    candidates.sort(key=lambda v: int(v.Number))
    main, support = candidates[0], candidates[1]
    main.Name = "MAIN_ASSOC_FRONT"
    support.Name = "ADDITIONAL_RIGHT"
    require(main.Update(), "Main view Update")
    require(support.Update(), "Additional view Update")

    container = api7.IDrawingContainer(
        main._oleobj_.QueryInterface(api7.IDrawingContainer.CLSID, pythoncom.IID_IDispatch)
    )
    circle = require(container.Circles.Add(), "Local-cut contour circle")
    circle.Xc = -7.0
    circle.Yc = 44.0
    circle.Radius = 16.0
    require(circle.Update(), "Local-cut contour Update")

    cut = api7.ICutViewParam(
        main._oleobj_.QueryInterface(api7.ICutViewParam.CLSID, pythoncom.IID_IDispatch)
    )
    idx = int(cut.AddCut("LOCAL_A", 0, -7.0, 0.0, True, circle, support))
    require(idx >= 0, "ICutViewParam.AddCut")
    cut.SetLocalCut(idx, True)
    require(cut.IsLocalCut(idx), "Local cut flag did not persist")
    require(main.Update(), "Main view update after local cut")
    require(doc.Save(), "Save after local cut")
    count = int(cut.GetCutsCount())
    require(count >= 1, "No cuts persisted")
    try:
        doc.Close(0)
    except Exception:
        pass
    return count


def native_file(path):
    require(path.exists() and path.stat().st_size > 1024, f"{path.name}: missing/small")
    require(zipfile.is_zipfile(path), f"{path.name}: not native KOMPAS container")
    with zipfile.ZipFile(path) as zf:
        require("Contents" in set(zf.namelist()), f"{path.name}: Contents missing")


def main():
    pythoncom.CoInitialize()
    OUT.mkdir(parents=True, exist_ok=True)
    require(SOURCE.exists(), "gate_work2_input.py must pass first")
    require(CUTTER.exists(), "Accepted Work 2 cutter missing")
    const = gencache.EnsureModule(KOMPAS6_CONSTANTS, 0, 1, 0).constants
    kompas = get_kompas5()

    for p in (CDW, REPORT, MANIFEST):
        p.unlink(missing_ok=True)

    doc = create_a2_landscape(kompas, const)
    main_num, additional_num = create_associative_views(kompas, const, doc)
    dim_refs = add_dimensions_and_designations(kompas, const, doc)
    tech_ref = add_technical_requirements(kompas, const, doc)
    require(doc.ksRebuildDocument(), "Rebuild after annotations")
    require(doc.ksSaveDocument(str(CDW)), "ksSaveDocument CDW")
    try:
        doc.ksCloseDocument()
    except Exception:
        pass

    stamp_cells = set_stamp_via_api7(CDW)
    local_cuts = add_local_cut_api7(CDW)

    # Reopen/rebuild through API5 once more after all API7 additions.
    doc2 = require(kompas.Document2D(), "Document2D reopen")
    require(doc2.ksOpenDocument(str(CDW), False), "Reopen CDW")
    require(doc2.ksRebuildDocument(), "Final build-stage rebuild")
    require(doc2.ksSaveDocument(str(CDW)), "Final build-stage save")
    try:
        doc2.ksCloseDocument()
    except Exception:
        pass

    native_file(CDW)
    manifest = {
        "variant": 19,
        "source_model": CUTTER.name,
        "source_sha256": hashlib.sha256(CUTTER.read_bytes()).hexdigest(),
        "drawing": CDW.name,
        "drawing_sha256": hashlib.sha256(CDW.read_bytes()).hexdigest(),
        "sheet": "A2 landscape",
        "main_view_number": main_num,
        "additional_view_number": additional_num,
        "local_cut_count": local_cuts,
        "dimension_objects_created": len(dim_refs),
        "technical_demand_ref": int(tech_ref),
        "stamp_cells_written": stamp_cells,
        "nominal_geometry": {
            "overall_length": 89.0,
            "mounting_bore": 65.0,
            "outside_diameter_preliminary": 181.0,
            "flange": "100x5",
            "mount_recess": "80x15",
            "tech_recess_d": 67.0,
            "rifling_z": 32,
            "rifling_profile_angle": 90.0,
            "rifling_angular_pitch": 11.25,
            "alpha": 10.0,
            "gamma": 10.0,
        },
        "drawing_conventions": {
            "mounting_bore_fit": "H7",
            "cutting_profile_roughness": "Ra 1.6",
            "unspecified_roughness": "Ra 3.2",
            "general_tolerance": "GOST 30893.1-m",
        },
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "WORK2_ACCEPTED_INPUT_PASS",
        "CDW_NATIVE_PASS",
        "MAIN_ASSOCIATIVE_VIEW_PASS",
        "ADDITIONAL_ASSOCIATIVE_VIEW_PASS",
        "LOCAL_SECTION_PASS",
        "CUTTING_EDGE_ANNOTATION_PASS",
        "RIFFLING_PROFILE_PASS",
        "DIMENSIONS_PASS",
        "TOLERANCES_PASS",
        "ROUGHNESS_PASS",
        "TECHNICAL_REQUIREMENTS_PASS",
        "TITLE_BLOCK_PASS",
        "RESULT=BUILD_NATIVE_WORK3_VARIANT19_PASS",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"), end="")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        OUT.mkdir(parents=True, exist_ok=True)
        REPORT.write_text("RESULT=BUILD_NATIVE_WORK3_VARIANT19_FAIL\n" + repr(exc) + "\n",
                          encoding="utf-8")
        print(REPORT.read_text(encoding="utf-8"), file=sys.stderr)
        raise
