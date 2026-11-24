"""Orchestrator. Independent path works without KOMPAS; native path is candidate-only until scope and review confirmed."""
from pathlib import Path
import argparse,csv,hashlib,json,os,shutil,subprocess,sys,zipfile,traceback
from engineering import load,models
HERE=Path(__file__).resolve().parent
NAMES=["01_Mechanism_Variant_06.frw","Work2_V19_Workpiece.m3d","Work2_V19_FormCutter.m3d","Work2_V19_TopDown.a3d","Work3_V19_FormCutter.cdw"]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def native_file(p):
    if not p.is_file() or p.stat().st_size<1024 or not zipfile.is_zipfile(p):raise RuntimeError("No valid modern native container: "+str(p))
    with zipfile.ZipFile(p) as z:
        if z.testzip() or not {"Contents","FileInfo"}<=set(z.namelist()):raise RuntimeError("Native container gate failed: "+str(p))
def exact_marker(path,marker):
    if marker not in path.read_text(encoding="utf-8-sig").splitlines():raise RuntimeError("Missing actual verification marker: "+marker)
def build(args):
    root=Path(args.out).resolve()
    if root.exists():raise FileExistsError("Use a fresh output directory: "+str(root))
    root.mkdir(parents=True)
    p=load(args.parameters)
    records={n:{"status":"BLOCKED","file_exists":False,"native_opened":False,"native_rebuilt":False,"native_reopened":False,"sha256":None,"size":None} for n in NAMES}
    manifest={"schema":1,"mode":args.mode,"parameters_sha256":sha(Path(args.parameters)),"scope_confirmed":p["scope"]["confirmed"],"groove_confirmed":p["work2"]["groove"]["confirmed"],"files":records,"steps":[],"status":"BLOCKED","final_zip_created":False}
    def save():
        (root/"acceptance_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    def block(reason):
        manifest["reason"]=reason;save();print(reason);return 2
    save()
    if args.mode=="native":
        if os.environ.get("KOMPAS_LICENSE_CONFIRMED")!="YES":return block("BLOCKED: confirm legal entitlement on the workstation first")
        if sys.platform!="win32":return block("BLOCKED: complete native route requires Windows COM API5/API7; Linux route only independent in this kit")
        if args.work=="all" and not args.candidate:return block("BLOCKED: figure 25 and scope unconfirmed; --candidate allows engineering trial only")
        if not args.candidate:return block("BLOCKED: --candidate required until original methodology and scope confirmed")
        try:
            import pythoncom,winreg
            for progid in ("KOMPAS.Application.7","Kompas.Application.5"):
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,progid+"\\CLSID") as key:winreg.QueryValueEx(key,None)
        except Exception as ex:return block("BLOCKED: COM preflight failed: "+repr(ex))
    try:
        engineering=root/"engineering"
        reference=models(p,engineering)
        manifest["steps"].append({"name":"independent_generation","status":"PASS_INTERMEDIATE","result":reference});save()
        if args.mode=="independent":
            manifest["status"]="PASS_INTERMEDIATE";save();return 0
        output=root/"native";output.mkdir()
        env=os.environ.copy()
        env.update({"KOMPAS_NATIVE_OUT":str(output),"KOMPAS_PARAMETERS":str(Path(args.parameters).resolve()),"KOMPAS_ENGINEERING_REFERENCE":str(engineering/"independent.json"),"KOMPAS_CANDIDATE_ONLY":"YES"})
        with (output/"calculation.csv").open("w",encoding="utf-8",newline="") as f:
            w=csv.DictWriter(f,fieldnames=["parameter","value","unit","status","source_or_formula"]);w.writeheader();w.writerows(p["work2"]["calculation"])
        def run(script,*extra):
            log=root/(Path(script).stem+".log")
            record={"name":script,"status":"RUNNING","log":log.name};manifest["steps"].append(record);save()
            try:
                with log.open("w",encoding="utf-8") as stream:
                    subprocess.run([sys.executable,str(HERE/script),*map(str,extra)],env=env,cwd=output,stdout=stream,stderr=subprocess.STDOUT,timeout=args.timeout,check=True)
                record["status"]="EXECUTED"
            except Exception as ex:
                record.update(status="FAIL",error=repr(ex));raise
            finally:save()
        def accept(name,evidence):
            f=output/name;native_file(f)
            records[name].update(status="PARTIAL",file_exists=True,native_opened=True,native_rebuilt=True,native_reopened=True,sha256=sha(f),size=f.stat().st_size,evidence=evidence,limitations="Candidate geometry only; scope, original method and visual release review unresolved.")
            save()
        frw=output/NAMES[0];extra=["--parameters",str(Path(args.parameters).resolve()),"--output",str(frw)]
        if args.seed:extra+=["--seed",str(Path(args.seed).resolve())]
        run("build_work1_native.py",*extra)
        ev=json.loads(frw.with_suffix(".verification.json").read_text())
        if len(ev["pre_save"])!=45 or len(ev["post_reopen"])!=45 or ev["sha256"]!=sha(frw):raise RuntimeError("FRW evidence incomplete")
        accept(NAMES[0],ev)
        if args.work=="all":
            run("build_work2_native.py");run("verify_work2_native.py")
            ver=output/"work2-verification.txt"
            exact_marker(ver,"RESULT=PASS_NATIVE_WORK2_VARIANT19_REOPEN_REBUILD_DEPENDENCY")
            for name in NAMES[1:4]:accept(name,ver.name)
            # Prepare the exact historical Work3 input gate only after its verifier succeeded.
            (output/"ACCEPTANCE.txt").write_text("RESULT=PASS_NATIVE_WORK2_VARIANT19\n",encoding="utf-8")
            (output/"SHA256.txt").write_text("".join(sha(output/n)+" "+n+"\n" for n in NAMES[1:4]),encoding="utf-8")
            run("gate_work2_input.py");run("build_work3_native.py");run("verify_work3_native.py")
            exact_marker(output/"work3-verification.txt","RESULT=PASS_NATIVE_WORK3_VARIANT19_ASSOCIATIVE_REBUILD")
            accept(NAMES[4],"work3-verification.txt")
            # Work3 verifies candidate dimensions and associative shape change, not final methodology or portability.
        manifest["status"]="PARTIAL_NATIVE_CANDIDATES"
        manifest["reason"]="Native execution tests do not establish original assignment scope, confirmed figure 25, complete feature parameterization or portable links; visual/manual release gate still required."
        save();return 0
    except Exception as ex:
        manifest["status"]="FAIL";manifest["reason"]=repr(ex)
        output=root/"native"
        for name,row in records.items():
            f=output/name
            if f.is_file():
                row.update(file_exists=True,sha256=sha(f),size=f.stat().st_size)
                if row["status"]=="BLOCKED":row["status"]="PARTIAL_UNVERIFIED"
        save();traceback.print_exc();return 1
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--mode",choices=["independent","native"],default="independent")
    ap.add_argument("--out",required=True)
    ap.add_argument("--parameters",default=str(HERE/"parameters.json"))
    ap.add_argument("--candidate",action="store_true")
    ap.add_argument("--work",choices=["1","all"],default="all")
    ap.add_argument("--seed",help="Optional original FRW; copied, never overwritten")
    ap.add_argument("--timeout",type=int,default=600)
    sys.exit(build(ap.parse_args()))
if __name__=="__main__":main()
