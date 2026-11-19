import os, pathlib, time, hashlib
import ksapi
from constants import constants as c

out = pathlib.Path(os.environ["STAGE4_OUT"])
app = None
for _ in range(60):
    app = ksapi.GetKompas()
    if app is not None:
        break
    time.sleep(1)

print("GETKOMPAS=", app)
if app is None:
    raise SystemExit("API7_GUI_ATTACH=UNAVAILABLE")

print("API7_GUI_ATTACH=AVAILABLE")
print("APP_NAME=", app.GetApplicationName(True))
print("BUILD=", app.GetBuildNumber())

try:
    app.SetVisible(True)
except Exception as exc:
    print("SET_VISIBLE_WARN=", repr(exc))

docs = app.GetDocuments()
if docs is None:
    raise SystemExit("GetDocuments returned None")

doc = None
try:
    doc = docs.AddWithDefaultSettings(c.ksDocumentDrawing, True)
    print("ADD_WITH_DEFAULT=", doc)
except Exception as exc:
    print("ADD_WITH_DEFAULT_ERROR=", repr(exc))

if doc is None:
    try:
        doc = docs.Add(c.ksDocumentDrawing, True)
        print("ADD=", doc)
    except Exception as exc:
        print("ADD_ERROR=", repr(exc))

if doc is None:
    raise SystemExit("DRAWING_CREATE_FAIL")

dtype = doc.GetDocumentType()
print("DOCUMENT_TYPE=", dtype)
print("EXPECTED_DRAWING_TYPE=", c.ksDocumentDrawing)
if dtype != c.ksDocumentDrawing:
    raise SystemExit("DOCUMENT_TYPE_NOT_DRAWING")
print("DOCUMENT_TYPE_DRAWING=PASS")

d2 = ksapi.IKompasDocument2D(doc)
vm = d2.GetViewsAndLayersManager()
views = vm.GetViews()
print("VIEWS_COUNT=", views.GetCount())
active = views.GetActiveView()
print("ACTIVE_VIEW=", active)
if active is None:
    raise SystemExit("NO_ACTIVE_DRAWING_VIEW")

ok = doc.SaveAs(str(out.resolve()))
print("SAVEAS=", ok)
if not out.exists() or out.stat().st_size <= 0:
    raise SystemExit("DRAWING_SAVE_FAIL")

print("CDW_SIZE=", out.stat().st_size)
print("CDW_SHA256=", hashlib.sha256(out.read_bytes()).hexdigest())
print("RESULT=PASS_REAL_DRAWING_CREATED_IN_FULL_GUI")
