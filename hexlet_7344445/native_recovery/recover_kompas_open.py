from __future__ import annotations
import hashlib, json, pathlib
import ksapi
from constants import constants as c

OUT=pathlib.Path("hexlet_7344445/native_recovery/kompas_open")
OUT.mkdir(parents=True,exist_ok=True)
target=OUT/"Hexlet_KOMPAS3D_Привет_Хекслет.cdw"
resaved=OUT/"Hexlet_KOMPAS3D_Привет_Хекслет_REOPENED.cdw"

app=ksapi.OpenKompas()
if app is None:
    raise SystemExit("OpenKompas returned None")
print("APP_NAME",app.GetApplicationName(True))
print("BUILD",app.GetBuildNumber())
app.SetVisible(True)

docs=app.GetDocuments()
if docs is None: raise SystemExit("GetDocuments None")
doc=docs.AddWithDefaultSettings(c.ksDocumentDrawing,True)
print("DOC",doc)
if doc is None: raise SystemExit("AddWithDefaultSettings drawing failed")
if doc.GetDocumentType()!=c.ksDocumentDrawing:
    raise SystemExit(f"Wrong document type {doc.GetDocumentType()}")

d2=ksapi.IKompasDocument2D(doc)
view=d2.GetViewsAndLayersManager().GetViews().GetActiveView()
dc=ksapi.IDrawingContainer(view)
texts=dc.GetDrawingTexts()
t=texts.Add()
t.SetX(70.0); t.SetY(120.0)
it=ksapi.IText(t)
line=it.Add()
item=line.Add()
item.SetStr("Привет, Хекслет!")
try: ksapi.ITextFont(item).SetHeight(10.0)
except Exception as exc: print("FONT_WARN",repr(exc))
if not t.Update(): raise SystemExit("Text Update false")
print("TEXT_COUNT_PRE_SAVE",texts.GetCount())

ok=doc.SaveAs(str(target.resolve()))
print("SAVE_OK",ok)
if not target.exists(): raise SystemExit("Target not saved")
sha=hashlib.sha256(target.read_bytes()).hexdigest()
print("TARGET_SHA256",sha,"SIZE",target.stat().st_size)

# Close native document, then open the file again through the same real application.
try:
    closed=doc.Close(c.kdDoNotSaveChanges)
    print("CLOSE_OK",closed)
except Exception as exc:
    print("CLOSE_WARN",type(exc).__name__,str(exc))
opened=docs.Open(str(target.resolve()),True,False)
if opened is None: raise SystemExit("REOPEN_FAIL")
print("REOPEN_TYPE",opened.GetDocumentType())
if opened.GetDocumentType()!=c.ksDocumentDrawing: raise SystemExit("REOPEN_WRONG_TYPE")
rd2=ksapi.IKompasDocument2D(opened)
rv=rd2.GetViewsAndLayersManager().GetViews().GetActiveView()
rdc=ksapi.IDrawingContainer(rv)
count=rdc.GetDrawingTexts().GetCount()
print("REOPEN_TEXT_COUNT",count)
if count<1: raise SystemExit("REOPEN_NO_TEXT")
ok2=opened.SaveAs(str(resaved.resolve()))
print("RESAVE_OK",ok2)
if not resaved.exists(): raise SystemExit("RESAVE_MISSING")

result={
 "result":"PASS_NATIVE_KOMPAS3D_OPENKOMPAS_DRAWING_REOPEN",
 "application":app.GetApplicationName(True),
 "build":app.GetBuildNumber(),
 "file":target.name,
 "sha256":sha,
 "size":target.stat().st_size,
 "reopen_type":opened.GetDocumentType(),
 "reopen_text_count":count,
 "resaved":resaved.name,
 "resaved_sha256":hashlib.sha256(resaved.read_bytes()).hexdigest()
}
(OUT/"validation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
print("RESULT=PASS_NATIVE_KOMPAS3D_OPENKOMPAS_DRAWING_REOPEN")
# Keep GUI alive briefly for framebuffer screenshot by outer shell.
import time
time.sleep(12)
app.Quit()
