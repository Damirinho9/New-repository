from __future__ import annotations
import hashlib, json, os, pathlib
import ksapi
from constants import constants as c

OUT=pathlib.Path("hexlet_7344445/native_recovery/kompas_donor")
OUT.mkdir(parents=True,exist_ok=True)
donor=pathlib.Path(os.environ["DONOR_CDW"])
target=OUT/"Hexlet_KOMPAS3D_Привет_Хекслет.cdw"
resaved=OUT/"Hexlet_KOMPAS3D_Привет_Хекслет_REOPENED.cdw"

app=ksapi.GetKompas()
if app is None:
    raise SystemExit("GetKompas returned None")
print("APP_NAME",app.GetApplicationName(True))
print("BUILD",app.GetBuildNumber())
print("DONOR",donor,donor.stat().st_size)

docs=app.GetDocuments()
doc=docs.Open(str(donor.resolve()),True,False)
print("OPEN",doc)
if doc is None:
    raise SystemExit("DONOR_OPEN_FAIL")
print("DONOR_TYPE",doc.GetDocumentType())
if doc.GetDocumentType()!=c.ksDocumentDrawing:
    raise SystemExit("DONOR_NOT_DRAWING")

d2=ksapi.IKompasDocument2D(doc)
view=d2.GetViewsAndLayersManager().GetViews().GetActiveView()
dc=ksapi.IDrawingContainer(view)

texts=dc.GetDrawingTexts()
before=texts.GetCount()
print("TEXT_COUNT_BEFORE",before)
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
after=texts.GetCount()
print("TEXT_COUNT_AFTER",after)
if after < before + 1:
    raise SystemExit("TEXT_NOT_ADDED")

ok=doc.SaveAs(str(target.resolve()))
print("SAVEAS_OK",ok)
if not target.exists() or target.stat().st_size==0:
    raise SystemExit("TARGET_MISSING")
print("TARGET_SIZE",target.stat().st_size)
print("TARGET_SHA256",hashlib.sha256(target.read_bytes()).hexdigest())
print("TARGET_HEAD",target.read_bytes()[:4].hex())
if target.read_bytes()[:2] != b"PK":
    raise SystemExit("TARGET_NOT_NATIVE_MODERN_CONTAINER")

try:
    closed=doc.Close(c.kdDoNotSaveChanges)
    print("CLOSE_OK",closed)
except Exception as exc:
    print("CLOSE_WARN",type(exc).__name__,str(exc))

opened=docs.Open(str(target.resolve()),True,False)
print("REOPEN",opened)
if opened is None:
    raise SystemExit("REOPEN_FAIL")
if opened.GetDocumentType()!=c.ksDocumentDrawing:
    raise SystemExit(f"REOPEN_TYPE_FAIL:{opened.GetDocumentType()}")
rd2=ksapi.IKompasDocument2D(opened)
rv=rd2.GetViewsAndLayersManager().GetViews().GetActiveView()
rdc=ksapi.IDrawingContainer(rv)
recount=rdc.GetDrawingTexts().GetCount()
print("REOPEN_TEXT_COUNT",recount)
if recount < after:
    raise SystemExit(f"TEXT_COUNT_LOST:{after}->{recount}")

ok2=opened.SaveAs(str(resaved.resolve()))
print("RESAVE_OK",ok2)
if not resaved.exists() or resaved.stat().st_size==0:
    raise SystemExit("RESAVED_MISSING")
print("RESAVED_SHA256",hashlib.sha256(resaved.read_bytes()).hexdigest())

result={
 "result":"PASS_NATIVE_KOMPAS3D_DONOR_SAVE_CLOSE_REOPEN",
 "application":app.GetApplicationName(True),
 "build":app.GetBuildNumber(),
 "donor":str(donor),
 "donor_sha256":hashlib.sha256(donor.read_bytes()).hexdigest(),
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
print("RESULT=PASS_NATIVE_KOMPAS3D_DONOR_SAVE_CLOSE_REOPEN")
