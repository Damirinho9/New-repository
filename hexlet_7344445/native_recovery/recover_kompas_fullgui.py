from __future__ import annotations
import hashlib, json, pathlib
import ksapi
from constants import constants as c

OUT=pathlib.Path("hexlet_7344445/native_recovery/kompas_fullgui")
OUT.mkdir(parents=True,exist_ok=True)
target=OUT/"Hexlet_KOMPAS3D_Привет_Хекслет.cdw"
resaved=OUT/"Hexlet_KOMPAS3D_Привет_Хекслет_REOPENED.cdw"

app=ksapi.GetKompas()
print("APP",app,flush=True)
if app is None:
    raise SystemExit("GetKompas returned None")
print("APP_NAME",app.GetApplicationName(True),flush=True)
print("BUILD",app.GetBuildNumber(),flush=True)

docs=app.GetDocuments()
if docs is None:
    raise SystemExit("GetDocuments returned None")

doc=docs.AddWithDefaultSettings(c.ksDocumentDrawing,True)
print("ADD_DEFAULT",doc,flush=True)
if doc is None:
    raise SystemExit("GUI AddWithDefaultSettings drawing failed")

d2=ksapi.IKompasDocument2D(doc)
view=d2.GetViewsAndLayersManager().GetViews().GetActiveView()
dc=ksapi.IDrawingContainer(view)
texts=dc.GetDrawingTexts()
before=texts.GetCount()
print("TEXT_COUNT_BEFORE",before,flush=True)

t=texts.Add()
t.SetX(60.0); t.SetY(120.0)
line=ksapi.IText(t).Add()
item=line.Add()
item.SetStr("Привет, Хекслет!")
try:
    ksapi.ITextFont(item).SetHeight(10.0)
except Exception as exc:
    print("FONT_WARN",type(exc).__name__,str(exc),flush=True)
if not t.Update():
    raise SystemExit("TEXT_UPDATE_FAIL")
after=texts.GetCount()
print("TEXT_COUNT_AFTER",after,flush=True)
if after < before + 1:
    raise SystemExit("TEXT_NOT_ADDED")

ok=doc.SaveAs(str(target.resolve()))
print("SAVEAS_OK",ok,flush=True)
if not target.exists() or target.stat().st_size==0:
    raise SystemExit("TARGET_NOT_SAVED")
print("TARGET_SIZE",target.stat().st_size,flush=True)
print("TARGET_SHA256",hashlib.sha256(target.read_bytes()).hexdigest(),flush=True)

try:
    closed=doc.Close(c.kdDoNotSaveChanges)
    print("CLOSE_OK",closed,flush=True)
except Exception as exc:
    print("CLOSE_WARN",type(exc).__name__,str(exc),flush=True)

opened=docs.Open(str(target.resolve()),True,False)
print("REOPEN",opened,flush=True)
if opened is None:
    raise SystemExit("REOPEN_FAIL")
if opened.GetDocumentType()!=c.ksDocumentDrawing:
    raise SystemExit(f"REOPEN_TYPE_FAIL:{opened.GetDocumentType()}")

rd2=ksapi.IKompasDocument2D(opened)
rv=rd2.GetViewsAndLayersManager().GetViews().GetActiveView()
rdc=ksapi.IDrawingContainer(rv)
recount=rdc.GetDrawingTexts().GetCount()
print("REOPEN_TEXT_COUNT",recount,flush=True)
if recount < after:
    raise SystemExit(f"TEXT_COUNT_LOST:{after}->{recount}")

ok2=opened.SaveAs(str(resaved.resolve()))
print("RESAVE_OK",ok2,flush=True)
if not resaved.exists() or resaved.stat().st_size==0:
    raise SystemExit("RESAVE_FAIL")

result={
 "result":"PASS_NATIVE_KOMPAS3D_FULLGUI_SAVE_CLOSE_REOPEN",
 "application":app.GetApplicationName(True),
 "build":app.GetBuildNumber(),
 "file":target.name,
 "size":target.stat().st_size,
 "sha256":hashlib.sha256(target.read_bytes()).hexdigest(),
 "text_count_before":before,
 "text_count_after":after,
 "reopen_text_count":recount,
 "resaved":resaved.name,
 "resaved_sha256":hashlib.sha256(resaved.read_bytes()).hexdigest()
}
(OUT/"validation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print("RESULT=PASS_NATIVE_KOMPAS3D_FULLGUI_SAVE_CLOSE_REOPEN",flush=True)
