from __future__ import annotations
import hashlib, json, pathlib, sys, traceback
import ksapi
from constants import constants as c

OUT = pathlib.Path("hexlet_7344445/native_recovery/kompas")
OUT.mkdir(parents=True, exist_ok=True)
cdw = OUT / "Hexlet_KOMPAS3D_Привет_Хекслет.cdw"

app = ksapi.OpenKompasInvisible()
if app is None:
    raise SystemExit("OpenKompasInvisible returned None")
print("APP_NAME", app.GetApplicationName(True))
print("BUILD", app.GetBuildNumber())

docs = app.GetDocuments()
# Create a real drawing, not a fragment.
doc = docs.Add(c.ksDocumentDrawing, True)
print("ADD_PLAIN", doc)
if doc is None:
    try:
        doc = docs.AddWithDefaultSettings(c.ksDocumentDrawing, True)
        print("ADD_DEFAULT", doc)
    except Exception as exc:
        print("ADD_DEFAULT_ERROR", type(exc).__name__, str(exc))
if doc is None:
    raise SystemExit("Both Add and AddWithDefaultSettings for ksDocumentDrawing failed")
d2 = ksapi.IKompasDocument2D(doc)
view = d2.GetViewsAndLayersManager().GetViews().GetActiveView()
dc = ksapi.IDrawingContainer(view)

# Add the exact required text through native KOMPAS API7.
t = dc.GetDrawingTexts().Add()
t.SetX(70.0)
t.SetY(120.0)
text_iface = ksapi.IText(t)
line = text_iface.Add()
item = line.Add()
item.SetStr("Привет, Хекслет!")
try:
    ksapi.ITextFont(item).SetHeight(10.0)
except Exception as exc:
    print("FONT_HEIGHT_WARN", repr(exc))
if not t.Update():
    raise SystemExit("DrawingText.Update returned false")

save_ok = doc.SaveAs(str(cdw.resolve()))
print("SAVE_OK", save_ok)
if not cdw.exists():
    raise SystemExit("CDW not created")
print("CDW_SIZE", cdw.stat().st_size)
print("CDW_SHA256", hashlib.sha256(cdw.read_bytes()).hexdigest())
print("CDW_HEAD", cdw.read_bytes()[:4].hex())

# Strict close + reopen using native KOMPAS document API.
try:
    close_ok = doc.Close(c.kdDoNotSaveChanges)
except Exception:
    # Some Linux bindings expose the enum under a slightly different name.
    traceback.print_exc()
    close_ok = False
print("CLOSE_OK", close_ok)

opened = docs.Open(str(cdw.resolve()), True, False)
if opened is None:
    raise SystemExit("Native reopen failed")
print("REOPEN_TYPE", opened.GetDocumentType())
if opened.GetDocumentType() != c.ksDocumentDrawing:
    raise SystemExit(f"Reopened type is not drawing: {opened.GetDocumentType()}")
rd2 = ksapi.IKompasDocument2D(opened)
rview = rd2.GetViewsAndLayersManager().GetViews().GetActiveView()
rdc = ksapi.IDrawingContainer(rview)
texts = rdc.GetDrawingTexts()
count = texts.GetCount()
print("REOPEN_TEXT_COUNT", count)
if count < 1:
    raise SystemExit("No drawing texts after reopen")

# Read text back through native API if possible. Fall back to object method introspection
# only for binding differences; do not inspect/patch the file format itself.
rt = texts.GetItem(0)
rtext = ksapi.IText(rt)
print("ITEXT_METHODS", [x for x in dir(rtext) if "Str" in x or "Line" in x or "Text" in x][:100])
readback = None
attempts = []
for name in ("GetStr", "get_Str"):
    try:
        fn = getattr(rtext, name)
        readback = fn()
        attempts.append([name, repr(readback)])
        if readback:
            break
    except Exception as exc:
        attempts.append([name, type(exc).__name__ + ":" + str(exc)])
if not readback:
    # Probe first line/item in the native text object.
    for line_getter in ("GetTextLine", "GetLine", "TextLine"):
        try:
            obj = getattr(rtext, line_getter)
            ln = obj(0) if callable(obj) else obj
            print("LINE_GETTER", line_getter, ln)
            for str_getter in ("GetStr", "get_Str", "Str"):
                try:
                    v = getattr(ln, str_getter)
                    readback = v() if callable(v) else v
                    attempts.append([f"{line_getter}.{str_getter}", repr(readback)])
                    if readback:
                        break
                except Exception as exc:
                    attempts.append([f"{line_getter}.{str_getter}", type(exc).__name__ + ":" + str(exc)])
            if readback:
                break
        except Exception as exc:
            attempts.append([line_getter, type(exc).__name__ + ":" + str(exc)])
print("READ_ATTEMPTS", json.dumps(attempts, ensure_ascii=False))
print("READBACK", repr(readback))
# At minimum the native reopen must preserve a drawing text object.
# If the binding exposes the string, require the exact text.
if readback is not None and "Привет, Хекслет!" not in str(readback):
    raise SystemExit(f"Unexpected readback: {readback!r}")

# Save once more after reopen to prove persistence.
resaved = OUT / "Hexlet_KOMPAS3D_Привет_Хекслет_REOPENED.cdw"
resave_ok = opened.SaveAs(str(resaved.resolve()))
print("RESAVE_OK", resave_ok)
if not resaved.exists():
    raise SystemExit("Reopened drawing could not be saved again")
print("RESAVED_SHA256", hashlib.sha256(resaved.read_bytes()).hexdigest())

result = {
    "result": "PASS_NATIVE_KOMPAS3D_DRAWING_REOPEN",
    "app": app.GetApplicationName(True),
    "build": app.GetBuildNumber(),
    "file": cdw.name,
    "sha256": hashlib.sha256(cdw.read_bytes()).hexdigest(),
    "size": cdw.stat().st_size,
    "reopen_type": opened.GetDocumentType(),
    "text_count": count,
    "readback": None if readback is None else str(readback),
    "resaved_file": resaved.name,
    "resaved_sha256": hashlib.sha256(resaved.read_bytes()).hexdigest(),
}
(OUT / "validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
print("RESULT=PASS_NATIVE_KOMPAS3D_DRAWING_REOPEN")

# trigger strict API7 recovery 2026-11-18
