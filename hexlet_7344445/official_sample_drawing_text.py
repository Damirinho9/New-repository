from __future__ import annotations
import hashlib, json, pathlib, sys
from pathlib import Path

sys.path.append('/opt/ascon/kompas3d-v25/Bin')
from constants import constants as c
import ksapi

OUT = pathlib.Path("official_pattern")
OUT.mkdir(parents=True, exist_ok=True)
cdw = OUT / "Hexlet_KOMPAS3D_Privet_Hexlet.cdw"
resaved = OUT / "Hexlet_KOMPAS3D_Privet_Hexlet_REOPENED.cdw"

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

# Exact official ASCON Linux sample pattern.
doc = docs.AddWithDefaultSettings(c.ksDocumentDrawing, True)
print("ADD_DEFAULT", doc)
if doc is None:
    raise SystemExit("official AddWithDefaultSettings drawing failed")

d2 = ksapi.IKompasDocument2D(doc)
mgr = d2.GetViewsAndLayersManager()
views = mgr.GetViews()
view = views.GetActiveView()
dc = ksapi.IDrawingContainer(view)
texts = dc.GetDrawingTexts()
print("TEXT_COUNT_BEFORE", texts.GetCount())

t = texts.Add()
print("DRAWING_TEXT", t)
if t is None:
    raise SystemExit("DrawingTexts.Add failed")
t.SetX(70.0)
t.SetY(120.0)
text_iface = ksapi.IText(t)
print("ITEXT", text_iface)

# Linux binding supports the structured IText -> line -> item route.
line = text_iface.Add()
print("TEXT_LINE", line)
if line is None:
    raise SystemExit("IText.Add line failed")
item = line.Add()
print("TEXT_ITEM", item)
if item is None:
    raise SystemExit("ITextLine.Add item failed")
item.SetStr("Привет, Хекслет!")
try:
    font = ksapi.ITextFont(item)
    font.SetHeight(10.0)
except Exception as exc:
    print("FONT_WARN", type(exc).__name__, str(exc))

updated = t.Update()
print("TEXT_UPDATE", updated)
if not updated:
    raise SystemExit("DrawingText.Update failed")
print("TEXT_COUNT_AFTER", texts.GetCount())

save = doc.SaveAs(str(cdw.resolve()))
print("SAVE", save)
if not cdw.exists() or cdw.stat().st_size == 0:
    raise SystemExit("CDW missing after SaveAs")
print("SIZE", cdw.stat().st_size)
print("SHA256", hashlib.sha256(cdw.read_bytes()).hexdigest())
print("HEAD", cdw.read_bytes()[:4])

close = doc.Close(c.kdDoNotSaveChanges)
print("CLOSE", close)

opened = docs.Open(str(cdw.resolve()), True, False)
print("REOPEN", opened)
if opened is None:
    raise SystemExit("native reopen failed")
dtype = opened.GetDocumentType()
print("REOPEN_TYPE", dtype)
if dtype != c.ksDocumentDrawing:
    raise SystemExit(f"wrong reopened type {dtype}")

rd2 = ksapi.IKompasDocument2D(opened)
rview = rd2.GetViewsAndLayersManager().GetViews().GetActiveView()
rdc = ksapi.IDrawingContainer(rview)
rtexts = rdc.GetDrawingTexts()
count = rtexts.GetCount()
print("REOPEN_TEXT_COUNT", count)
if count < 1:
    raise SystemExit("text object missing after reopen")

# Read back native text structure if the binding exposes it.
readback = None
try:
    rt = rtexts.GetItem(0)
    rit = ksapi.IText(rt)
    print("REOPEN_ITEXT", rit)
    for method in ("GetStr",):
        if hasattr(rit, method):
            try:
                readback = getattr(rit, method)()
                print("READBACK_DIRECT", repr(readback))
            except Exception as exc:
                print("READBACK_DIRECT_ERR", type(exc).__name__, str(exc))
except Exception as exc:
    print("READBACK_WARN", type(exc).__name__, str(exc))

save2 = opened.SaveAs(str(resaved.resolve()))
print("RESAVE", save2)
if not resaved.exists() or resaved.stat().st_size == 0:
    raise SystemExit("reopened resave missing")

validation = {
    "result":"PASS_NATIVE_OFFICIAL_PATTERN_CDW_TEXT_REOPEN",
    "application":app.GetApplicationName(True),
    "build":app.GetBuildNumber(),
    "file":cdw.name,
    "size":cdw.stat().st_size,
    "sha256":hashlib.sha256(cdw.read_bytes()).hexdigest(),
    "reopen_type":dtype,
    "reopen_text_count":count,
    "readback":readback,
    "resaved_sha256":hashlib.sha256(resaved.read_bytes()).hexdigest(),
}
(OUT/"validation.json").write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding="utf-8")
print("RESULT=PASS_NATIVE_OFFICIAL_PATTERN_CDW_TEXT_REOPEN")
app.Quit()
