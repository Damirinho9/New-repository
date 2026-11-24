from pathlib import Path
import base64, hashlib, zipfile, json
from geometry import audit
audit()
root=Path(__file__).resolve().parent.parent
parts=sorted((root/"kompas-input").glob("v6.b64.part*"))
assert len(parts)==8
data=base64.b64decode("".join(p.read_text().strip() for p in parts),validate=True)
assert len(data)==71953, len(data)
out=root/"native-resume"/"recovered"
out.mkdir(exist_ok=True)
p=out/"01_Mekhanizm_Variant_06_ORIGINAL.frw"
p.write_bytes(data)
with zipfile.ZipFile(p) as z:
    assert z.testzip() is None
    names=z.namelist()
    assert "Contents" in names and "FileInfo" in names
info={"status":"ORIGINAL_STATIC_RECOVERY_ONLY","size":len(data),"sha256":hashlib.sha256(data).hexdigest(),"members":names,"native_editing_verified":False}
(out/"recovery.json").write_text(json.dumps(info,indent=2))
print(json.dumps(info,indent=2))
