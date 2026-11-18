from __future__ import annotations
import hashlib, json, os, pathlib
import ksapi
from constants import constants as c

OUT=pathlib.Path("hexlet_7344445/native_recovery/kompas_template")
OUT.mkdir(parents=True,exist_ok=True)
donor=pathlib.Path(os.environ["DONOR_CDW"])
target=OUT/"Hexlet_KOMPAS3D_Привет_Хекслет.cdw"

app=ksapi.GetKompas()
if app is None: raise SystemExit("GetKompas=None")
print("APP",app.GetApplicationName(True),app.GetBuildNumber())
docs=app.GetDocuments()
doc=docs.Open(str(donor.resolve()),True,False)
if doc is None: raise SystemExit("DONOR_OPEN_FAIL")
print("DONOR_TYPE",doc.GetDocumentType())
if doc.GetDocumentType()!=c.ksDocumentDrawing: raise SystemExit("DONOR_NOT_DRAWING")

d2=ksapi.IKompasDocument2D(doc)
view=d2.GetViewsAndLayersManager().GetViews().GetActiveView()
dc=ksapi.IDrawingContainer(view)
sc=ksapi.ISymbols2DContainer(view)

# Delete geometric/symbol objects in the active view using KOMPAS' own API.
deleted={}
for container,getter in [
    (dc,"GetColourings"),(dc,"GetDrawingContours"),(dc,"GetDrawingTexts"),
    (sc,"GetLineDimensions"),(sc,"GetRadialDimensions"),(sc,"GetDiametralDimensions"),(sc,"GetAngleDimensions"),
    (dc,"GetLineSegments"),(dc,"GetCircles"),(dc,"GetPoints"),(dc,"GetArcs"),(dc,"GetRegularPolygons")
]:
    try:
        col=getattr(container,getter)()
        n=col.GetCount()
        for i in reversed(range(n)):
            try: col.GetItem(i).Delete()
            except Exception as exc: print("DELETE_WARN",getter,i,type(exc).__name__,str(exc))
        deleted[getter]=n
    except Exception as exc:
        deleted[getter]="ERR:"+type(exc).__name__+":"+str(exc)
print("DELETED",json.dumps(deleted,ensure_ascii=False))

# Add exact required phrase as native drawing text.
t=dc.GetDrawingTexts().Add()
t.SetX(60.0); t.SetY(120.0)
item=ksapi.IText(t).Add().Add()
item.SetStr("Привет, Хекслет!")
try: ksapi.ITextFont(item).SetHeight(10.0)
except Exception as exc: print("FONT_WARN",repr(exc))
if not t.Update(): raise SystemExit("TEXT_UPDATE_FAIL")
print("TEXT_COUNT_BEFORE_SAVE",dc.GetDrawingTexts().GetCount())

ok=doc.SaveAs(str(target.resolve()))
print("SAVEAS_OK",ok)
if not target.exists(): raise SystemExit("TARGET_MISSING")
print("TARGET_SIZE",target.stat().st_size)
print("TARGET_SHA256",hashlib.sha256(target.read_bytes()).hexdigest())

# Re-open the saved native CDW in the same real application as an independent document.
opened=docs.Open(str(target.resolve()),True,False)
if opened is None: raise SystemExit("REOPEN_FAIL")
print("REOPEN_TYPE",opened.GetDocumentType())
if opened.GetDocumentType()!=c.ksDocumentDrawing: raise SystemExit("REOPEN_NOT_DRAWING")
rd2=ksapi.IKompasDocument2D(opened)
rv=rd2.GetViewsAndLayersManager().GetViews().GetActiveView()
rdc=ksapi.IDrawingContainer(rv)
count=rdc.GetDrawingTexts().GetCount()
print("REOPEN_TEXT_COUNT",count)
if count<1: raise SystemExit("REOPEN_NO_TEXT")

# Resave after reopen for persistence proof.
resaved=OUT/"Hexlet_KOMPAS3D_Привет_Хекслет_REOPENED.cdw"
ok2=opened.SaveAs(str(resaved.resolve()))
print("RESAVE_OK",ok2)
if not resaved.exists(): raise SystemExit("RESAVED_MISSING")
print("RESAVED_SHA256",hashlib.sha256(resaved.read_bytes()).hexdigest())

result={
  "result":"PASS_NATIVE_KOMPAS3D_TEMPLATE_SAVE_REOPEN",
  "application":app.GetApplicationName(True),
  "build":app.GetBuildNumber(),
  "donor":str(donor),
  "file":target.name,
  "sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
  "size":target.stat().st_size,
  "reopen_type":opened.GetDocumentType(),
  "reopen_text_count":count,
  "deleted":deleted,
  "resaved":resaved.name,
  "resaved_sha256":hashlib.sha256(resaved.read_bytes()).hexdigest()
}
(OUT/"validation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print("RESULT=PASS_NATIVE_KOMPAS3D_TEMPLATE_SAVE_REOPEN")
