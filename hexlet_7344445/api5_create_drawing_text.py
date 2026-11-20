from __future__ import annotations
import hashlib, pathlib, sys, traceback
import ksapi
from constants import constants as c

OUT = pathlib.Path("api5_native")
OUT.mkdir(exist_ok=True)
target = (OUT / "Hexlet_KOMPAS3D_Privet_Hexlet.cdw").resolve()

def wrap(name, obj):
    cls = getattr(ksapi, name, None)
    if cls is None:
        print("WRAPPER_MISSING", name)
        return obj
    try:
        w = cls(obj)
        print("WRAPPED", name, w)
        return w
    except Exception as exc:
        print("WRAP_FAIL", name, type(exc).__name__, str(exc))
        return obj

def set_value(obj, prop, value):
    setter = "Set" + prop[0].upper() + prop[1:]
    if hasattr(obj, setter):
        try:
            r = getattr(obj, setter)(value)
            print("SETTER", setter, value, r)
            return
        except Exception as exc:
            print("SETTER_FAIL", setter, type(exc).__name__, str(exc))
    try:
        setattr(obj, prop, value)
        print("PROP_SET", prop, value)
        return
    except Exception as exc:
        print("PROP_FAIL", prop, type(exc).__name__, str(exc))
    raise RuntimeError(f"cannot set {prop}")

app = ksapi.GetKompas()
print("APP=", app)
if app is None:
    raise SystemExit("GetKompas returned None")
print("APP_NAME=", app.GetApplicationName(True))
print("BUILD=", app.GetBuildNumber())

print("HAS_DOCUMENT2D", hasattr(app, "Document2D"))
print("HAS_GETPARAMSTRUCT", hasattr(app, "GetParamStruct"))
print("KO_DOCUMENTPARAM", getattr(c, "ko_DocumentParam", None))
print("LT_DOCSHEET", getattr(c, "lt_DocSheetStandart", None))

raw_param = app.GetParamStruct(c.ko_DocumentParam)
print("RAW_PARAM=", raw_param)
if raw_param is None:
    raise SystemExit("GetParamStruct(ko_DocumentParam) failed")
param = wrap("ksDocumentParam", raw_param)
if hasattr(param, "Init"):
    print("PARAM_INIT=", param.Init())

set_value(param, "type", c.lt_DocSheetStandart)
try:
    set_value(param, "regime", 1)
except Exception:
    try:
        set_value(param, "regim", 1)
    except Exception as exc:
        print("REGIME_WARN", type(exc).__name__, str(exc))

raw_doc = app.Document2D()
print("RAW_DOC=", raw_doc)
if raw_doc is None:
    raise SystemExit("Document2D() returned None")
doc = wrap("ksDocument2D", raw_doc)

print("DOC_METHODS", [n for n in dir(doc) if any(k.lower() in n.lower() for k in ["create","text","save","open","close","type"])])
create = doc.ksCreateDocument(param)
print("CREATE_RESULT=", create)
if not create:
    raise SystemExit("ksCreateDocument failed")

try:
    dtype = doc.ksGetDocumentType()
    print("DOC_TYPE=", dtype)
except Exception as exc:
    print("DOC_TYPE_WARN", type(exc).__name__, str(exc))

text_ref = doc.ksText(60.0, 120.0, 0.0, 10.0, 1.0, 0, "Привет, Хекслет!")
print("TEXT_REF=", text_ref)
if not text_ref:
    raise SystemExit("ksText failed")

save = doc.ksSaveDocument(str(target))
print("SAVE_RESULT=", save)
if not save:
    raise SystemExit("ksSaveDocument failed")
if not target.exists() or target.stat().st_size == 0:
    raise SystemExit("saved CDW missing/empty")
print("SIZE=", target.stat().st_size)
print("SHA256=", hashlib.sha256(target.read_bytes()).hexdigest())
print("HEAD=", target.read_bytes()[:4])

try:
    close = doc.ksCloseDocument()
    print("CLOSE_RESULT=", close)
except TypeError:
    close = doc.ksCloseDocument(0)
    print("CLOSE_RESULT_ARG0=", close)
except Exception as exc:
    print("CLOSE_WARN=", type(exc).__name__, str(exc))

raw_doc2 = app.Document2D()
doc2 = wrap("ksDocument2D", raw_doc2)
opened = doc2.ksOpenDocument(str(target), 1)
print("REOPEN_RESULT=", opened)
if not opened:
    raise SystemExit("ksOpenDocument reopen failed")
try:
    dtype2 = doc2.ksGetDocumentType()
    print("REOPEN_DOC_TYPE=", dtype2)
except Exception as exc:
    print("REOPEN_TYPE_WARN", type(exc).__name__, str(exc))

# A second save proves the reopened document remains a valid native editable document.
target2 = (OUT / "Hexlet_KOMPAS3D_Privet_Hexlet_REOPENED.cdw").resolve()
save2 = doc2.ksSaveDocument(str(target2))
print("RESAVE_RESULT=", save2)
if not save2 or not target2.exists() or target2.stat().st_size == 0:
    raise SystemExit("reopened document resave failed")
print("RESAVE_SIZE=", target2.stat().st_size)
print("RESAVE_SHA256=", hashlib.sha256(target2.read_bytes()).hexdigest())

print("RESULT=PASS_NATIVE_API5_CDW_TEXT_SAVE_REOPEN")
