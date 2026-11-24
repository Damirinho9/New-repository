"""Stage 7 A/B candidate: factory-only gate, not production acceptance.
Run only on an independently verified, legitimately licensed KOMPAS backend.
This script never activates a license or changes license files.
"""
import argparse
import pathlib
import json
import os
import shutil
import sys
import zipfile

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sample", required=True, type=pathlib.Path)
    p.add_argument("--out", required=True, type=pathlib.Path)
    a = p.parse_args()
    # Operator-controlled safeguard, not a substitute for actual license evidence.
    if os.environ.get("KOMPAS_COMMERCIAL_CONFIRMED") != "1":
        raise SystemExit("BLOCKED: no independently confirmed commercial entitlement")
    import ksapi
    from constants import constants as c
    a.out.mkdir(parents=True, exist_ok=True)
    sample = a.out / "input-copy.frw"
    if sample.exists():
        raise SystemExit("Refusing to overwrite test input")
    shutil.copyfile(a.sample, sample)
    app = ksapi.GetKompas()
    if not app:
        raise SystemExit("NO_SDK_CONNECTION")
    manager = app.GetApplicationLicenseManager()
    if not manager:
        raise SystemExit("NO_LICENSE_MANAGER")
    docs = app.GetDocuments()
    previous = docs.IsLockTemplatesSettings()
    results = []
    def param_open(path):
        param = docs.GetOpenDocumentParam()
        if not param:
            raise RuntimeError("NO_OPEN_PARAM")
        param.SetVisible(False)
        param.SetReadOnly(False)
        return docs.OpenDocument(str(path.resolve()), param)
    def trial(name, typ, ext, factory):
        doc = None
        reopened = None
        record = {"route":name,"type":ext,"status":"FAIL"}
        dest = a.out / (name + "." + ext)
        try:
            if dest.exists():
                raise RuntimeError("REFUSE_OVERWRITE")
            doc = factory()
            if not doc:
                raise RuntimeError("NULL_FACTORY")
            if doc.GetDocumentType() != typ:
                raise RuntimeError("WRONG_TYPE")
            if ext in ("m3d","a3d"):
                if not ksapi.IKompasDocument3D(doc).GetTopPart():
                    raise RuntimeError("NO_TOPPART")
            if not doc.SaveAs(str(dest.resolve())):
                raise RuntimeError("SAVE_FAILED")
            if not doc.Close(c.kdDoNotSaveChanges):
                raise RuntimeError("CLOSE_FAILED")
            doc = None
            with zipfile.ZipFile(dest) as z:
                if z.testzip() is not None or not {"Contents","FileInfo"} <= set(z.namelist()):
                    raise RuntimeError("BAD_NATIVE_CONTAINER")
            reopened = param_open(dest)
            if not reopened or reopened.GetDocumentType() != typ:
                raise RuntimeError("REOPEN_FAILED")
            record["status"] = "FACTORY_SAVE_REOPEN_ONLY"
        except Exception as exc:
            record["error"] = repr(exc)
        finally:
            for obj in (reopened,doc):
                if obj:
                    try: obj.Close(c.kdDoNotSaveChanges)
                    except Exception: pass
            results.append(record)
            print(json.dumps(record), flush=True)
    try:
        docs.SetLockTemplatesSettings(True)
        if not docs.IsLockTemplatesSettings():
            raise RuntimeError("TEMPLATE_LOCK_NOT_SET")
        for ext,typ,module in (
            ("frw",c.ksDocumentFragment,c.ksKompasModule2D),
            ("cdw",c.ksDocumentDrawing,c.ksKompasModule2D),
            ("m3d",c.ksDocumentPart,c.ksKompasModule3D),
            ("a3d",c.ksDocumentAssembly,c.ksKompasModule3D)):
            if not manager.IsKompasModuleActive(module):
                results.append({"type":ext,"status":"MODULE_INACTIVE"})
                continue
            trial("A_add_"+ext,typ,ext,lambda: docs.Add(typ,False))
            if results[-1]["status"] != "FACTORY_SAVE_REOPEN_ONLY":
                trial("A_default_"+ext,typ,ext,lambda:docs.AddWithDefaultSettings(typ,False))
        if manager.IsKompasModuleActive(c.ksKompasModule2D):
            trial("B_explicit_open",c.ksDocumentFragment,"frw",lambda:param_open(sample))
    finally:
        docs.SetLockTemplatesSettings(previous)
        (a.out/"factory-results.json").write_text(json.dumps(results,indent=2),encoding="utf-8")
    return 0 if any(r["status"]=="FACTORY_SAVE_REOPEN_ONLY" for r in results) else 1

if __name__ == "__main__":
    sys.exit(main())
