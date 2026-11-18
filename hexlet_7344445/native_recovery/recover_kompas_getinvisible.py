from __future__ import annotations
import hashlib, json, pathlib, os, sys, traceback
import ksapi
from constants import constants as c

OUT=pathlib.Path("hexlet_7344445/native_recovery/kompas_getinvisible")
OUT.mkdir(parents=True,exist_ok=True)
target=OUT/"Hexlet_KOMPAS3D_Привет_Хекслет.cdw"
resaved=OUT/"Hexlet_KOMPAS3D_Привет_Хекслет_REOPENED.cdw"

app=ksapi.GetKompasInvisible()
print("APP",app)
if app is None:
    raise SystemExit("GetKompasInvisible returned None")
print("APP_NAME",app.GetApplicationName(True))
print("BUILD",app.GetBuildNumber())

docs=app.GetDocuments()
print("DOCS",docs)
if docs is None:
    raise SystemExit("GetDocuments returned None")

doc=docs.AddWithDefaultSettings(c.ksDocumentDrawing,True)
print("ADD_DEFAULT",doc)
if doc is None:
    try:
        err=app.GetKompasError()
        print("KOMPAS_ERROR",err)
    except Exception as exc:
        print("ERROR_QUERY_WARN",type(exc).__name__,str(exc))
    raise SystemExit("AddWithDefaultSettings failed")

d2=ksapi.IKompasDocument2D(doc)
view=d2.GetViewsAndLayersManager().GetViews().GetActiveView()
dc=ksapi.IDrawingContainer(view)
texts=dc.GetDrawingTexts()
print("TEXTS_BEFORE",texts.GetCount())
t=texts.Add()
t.SetX(60.0); t.SetY(120.0)
it=ksapi.IText(t)
line=it.Add()
item=line.Add()
item.SetStr("Привет, Хекслет!")
try:
    ksapi.ITextFont(item).SetHeight(10.0)
except Exception as exc:
    print("FONT_WARN",type(exc).__name__,str(exc))
if not t.Update():
    raise SystemExit("TEXT_UPDATE_FAIL")
print("TEXTS_AFTER",texts.GetCount())

ok=doc.SaveAs(str(target.resolve()))
print("SAVE_OK",ok)
if not target.exists() or target.stat().st_size==0:
    raise SystemExit("TARGET_NOT_SAVED")
print("TARGET_SIZE",target.stat().st_size)
print("TARGET_SHA256",hashlib.sha256(target.read_bytes()).hexdigest())

try:
    closed=doc.Close(c.kdDoNotSaveChanges)
    print("CLOSE_OK",closed)
except Exception as exc:
    print("CLOSE_WARN",type(exc).__name__,str(exc))

opened=docs.Open(str(target.resolve()),True,False)
print("REOPEN",opened)
if opened is None:
    raise SystemExit("REOPEN_FAIL")
print("REOPEN_TYPE",opened.GetDocumentType())
rd2=ksapi.IKompasDocument2D(opened)
rv=rd2.GetViewsAndLayersManager().GetViews().GetActiveView()
rdc=ksapi.IDrawingContainer(rv)
count=rdc.GetDrawingTexts().GetCount()
print("REOPEN_TEXT_COUNT",count)
if count<1:
    raise SystemExit("REOPEN_NO_TEXT")

ok2=opened.SaveAs(str(resaved.resolve()))
print("RESAVE_OK",ok2)
if not resaved.exists() or resaved.stat().st_size==0:
    raise SystemExit("RESAVE_FAIL")

result={
 "result":"PASS_NATIVE_KOMPAS3D_GETINVISIBLE_SAVE_CLOSE_REOPEN",
 "application":app.GetApplicationName(True),
 "build":app.GetBuildNumber(),
 "file":target.name,
 "size":target.stat().st_size,
 "sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
 "reopen_type":opened.GetDocumentType(),
 "reopen_text_count":count,
 "resaved":resaved.name,
 "resaved_sha256":hashlib.sha256(resaved.read_bytes()).hexdigest()
}
(OUT/"validation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print("RESULT=PASS_NATIVE_KOMPAS3D_GETINVISIBLE_SAVE_CLOSE_REOPEN")
