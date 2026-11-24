"""Validate Python syntax, contract and strict blocked-mode behavior without any CAD license."""
import ast,json,os,subprocess,sys,tempfile
from pathlib import Path
from engineering import load,check_mechanics
HERE=Path(__file__).resolve().parent
def main():
    files=list(HERE.glob("*.py"))
    for f in files:ast.parse(f.read_text(encoding="utf-8-sig"),filename=str(f))
    p=load();assert check_mechanics(p)==3607
    with tempfile.TemporaryDirectory() as d:
        target=Path(d)/"blocked";env=os.environ.copy();env.pop("KOMPAS_LICENSE_CONFIRMED",None)
        run=subprocess.run([sys.executable,str(HERE/"native_build.py"),"--mode","native","--out",str(target)],env=env,check=False)
        assert run.returncode==2
        m=json.loads((target/"acceptance_manifest.json").read_text())
        assert m["status"]=="BLOCKED" and not m["final_zip_created"]
        assert all(x["status"]=="BLOCKED" and not x["file_exists"] for x in m["files"].values())
        assert not (target/"native").exists()
    print("PASS: syntax",len(files),"Python scripts; 3607 geometry states; fail-closed entitlement gate")
if __name__=="__main__":main()
