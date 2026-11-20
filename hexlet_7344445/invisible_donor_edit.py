from __future__ import annotations
import hashlib, json, pathlib, sys, traceback

sys.path.append('/opt/ascon/kompas3d-v25/Bin')
from constants import constants as c
import ksapi

OUT = pathlib.Path("donor_edit")
OUT.mkdir(exist_ok=True)
donor = pathlib.Path("/opt/ascon/kompas3d-v25/Samples/Drawings/SAMPLE4.cdw")
target = (OUT / "Hexlet_KOMPAS3D_Privet_Hexlet.cdw").resolve()
resaved = (OUT / "Hexlet_KOMPAS3D_Privet_Hexlet_REOPENED.cdw").resolve()

print("DONOR", donor, donor.exists(), donor.stat().st_size if donor.exists() else None)
if not donor.exists():
    raise SystemExit("official donor missing")

app = ksapi.OpenKompasInvisible()
print("APP", app)
if app is None:
    raise SystemExit("OpenKompasInvisible returned None")
print("APP_NAME", app.GetApplicationName(True))
print("BUILD", app.GetBuildNumber())

docs = app.GetDocuments()
print("DOCS", docs)
if docs is None:
    raise SystemExit("GetDocuments returned None")

doc = docs.Open(str(donor.resolve()), True, False)
print("OPEN_DONOR", doc)
if doc is None:
    raise SystemExit("official donor open returned None")
dtype = doc.GetDocumentType()
print("DONOR_TYPE", dtype)
if dtype != c.ksDocumentDrawing:
    raise SystemExit(f"donor type not drawing: {dtype}")

d2 = ksapi.IKompasDocument2D(doc)
views = d2.GetViewsAndLayersManager().GetViews()
view = views.GetActiveView()
print("ACTIVE_VIEW", view)
if view is None:
    # fallback to system view 0
    try:
        view = views.ViewByNumber(0)
        print("VIEW0", view)
    except Exception as exc:
        print("VIEW0_ERR", type(exc).__name__, str(exc))
if view is None:
    raise SystemExit("no active/system view")

dc = ksapi.IDrawingContainer(view)
texts = dc.GetDrawingTexts()
before = texts.GetCount()
print("TEXT_COUNT_BEFORE", before)

t = texts.Add()
print("TEXT_OBJECT", t)
if t is None:
    raise SystemExit("DrawingTexts.Add returned None")
t.SetX(70.0)
t.SetY(120.0)

it = ksapi.IText(t)
line = it.Add()
print("TEXT_LINE", line)
if line is None:
    raise SystemExit("IText.Add returned None")
item = line.Add()
print("TEXT_ITEM", item)
if item is None:
    raise SystemExit("line.Add returned None")
item.SetStr("Привет, Хекслет!")
try:
    ksapi.ITextFont(item).SetHeight(10.0)
except Exception as exc:
    print("FONT_WARN", type(exc).__name__, str(exc))

updated = t.Update()
print("TEXT_UPDATE", updated)
if not updated:
    raise SystemExit("DrawingText.Update returned false")
after = texts.GetCount()
print("TEXT_COUNT_AFTER", after)
if after < before + 1:
    raise SystemExit(f"text count did not increase: {before}->{after}")

save = doc.SaveAs(str(target))
print("SAVEAS", save)
if not target.exists() or target.stat().st_size == 0:
    raise SystemExit("target not saved")
print("TARGET_SIZE", target.stat().st_size)
print("TARGET_SHA256", hashlib.sha256(target.read_bytes()).hexdigest())
print("TARGET_HEAD", target.read_bytes()[:4].hex())

try:
    close = doc.Close(c.kdDoNotSaveChanges)
    print("CLOSE", close)
except Exception as exc:
    print("CLOSE_WARN", type(exc).__name__, str(exc))

opened = docs.Open(str(target), True, False)
print("REOPEN_TARGET", opened)
if opened is None:
    raise SystemExit("target reopen failed")
print("REOPEN_TYPE", opened.GetDocumentType())
if opened.GetDocumentType() != c.ksDocumentDrawing:
    raise SystemExit("reopened type not drawing")

rd2 = ksapi.IKompasDocument2D(opened)
rviews = rd2.GetViewsAndLayersManager().GetViews()
rview = rviews.GetActiveView()
if rview is None:
    try: rview = rviews.ViewByNumber(0)
    except Exception: pass
if rview is None:
    raise SystemExit("no view after reopen")

rdc = ksapi.IDrawingContainer(rview)
rtexts = rdc.GetDrawingTexts()
recount = rtexts.GetCount()
print("REOPEN_TEXT_COUNT", recount)
if recount < before + 1:
    raise SystemExit(f"new text lost on reopen: before={before}, reopen={recount}")

save2 = opened.SaveAs(str(resaved))
print("RESAVE", save2)
if not resaved.exists() or resaved.stat().st_size == 0:
    raise SystemExit("resave missing")
print("RESAVE_SHA256", hashlib.sha256(resaved.read_bytes()).hexdigest())

validation = {
    "result": "PASS_NATIVE_DONOR_EDIT_TEXT_REOPEN",
    "application": app.GetApplicationName(True),
    "build": app.GetBuildNumber(),
    "donor": str(donor),
    "text_count_before": before,
    "text_count_after": after,
    "reopen_text_count": recount,
    "target": target.name,
    "size": target.stat().st_size,
    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
    "resaved_sha256": hashlib.sha256(resaved.read_bytes()).hexdigest(),
}
(OUT/"validation.json").write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding="utf-8")
print("RESULT=PASS_NATIVE_DONOR_EDIT_TEXT_REOPEN")
app.Quit()
