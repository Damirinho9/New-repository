import csv, json, math, os, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"stage3-out"
OUT.mkdir(parents=True,exist_ok=True)
builder=ROOT/"fullv6"/"build_stage3_sim.py"

currents_uA=[0.0,0.2,0.5,0.8,1.0,1.2,1.5,2.0,2.5,3.0,4.0]
nets=["sens","u_ctrl","t1","t2","drv","g1","g2","l","sw"]

def run(cmd,log):
    p=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",errors="replace")
    Path(log).write_text((p.stdout or "")+"\n--- STDERR ---\n"+(p.stderr or ""),encoding="utf-8")
    return p

def metrics(csv_path,tail_start=0.6):
    rows=[]
    with open(csv_path,newline="",encoding="utf-8") as f:
        rd=csv.DictReader(f)
        for r in rd:
            t=float(r["time"])
            if t>=tail_start:
                rows.append({k:float(v) for k,v in r.items()})
    if not rows:
        return {}
    def stats(vals):
        n=len(vals); mean=sum(vals)/n
        return {"mean":mean,"rms":math.sqrt(sum(x*x for x in vals)/n),"min":min(vals),"max":max(vals),"pp":max(vals)-min(vals)}
    out={n:stats([r[n] for r in rows]) for n in nets}
    load=[r["l"]-r["sw"] for r in rows]
    out["load_v"]=stats(load)
    out["points_tail"]=len(rows)
    return out

results=[]
for u in currents_uA:
    state=("scan_"+str(u).replace(".","p")+"uA")
    iph=u*1e-6
    b=run([sys.executable,str(builder),state,str(iph)],OUT/f"{state}_build.log")
    ms14=OUT/f"7330744_PhotoRelay_V6_SIM_{state}.ms14"
    rec={"photocurrent_uA":u,"state":state,"build_rc":b.returncode}
    if b.returncode!=0 or not ms14.exists():
        rec["failure"]="build"; results.append(rec); continue
    csvdir=OUT/f"{state}_csv"
    s=run([sys.executable,"-m","multisimforge","sim",str(ms14),"--nets",",".join(nets),"--tran","0.8,8000","--csv",str(csvdir)],OUT/f"{state}_sim.log")
    rec["sim_rc"]=s.returncode
    try:
        txt=(s.stdout or "").strip()
        rec["sim_json"]=json.loads(txt) if txt.startswith("{") else {}
    except Exception as e:
        rec["sim_json_error"]=str(e)
    tran=csvdir/"tran.csv"
    if tran.exists():
        rec["metrics"]=metrics(tran)
    else:
        rec["failure"]="no_csv"
    results.append(rec)
    Path(OUT/"scan_progress.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")

ok=[r for r in results if r.get("metrics")]
if ok:
    lo=min(ok,key=lambda r:r["photocurrent_uA"])
    hi=max(ok,key=lambda r:r["photocurrent_uA"])
    a=lo["metrics"]["load_v"]["rms"]; b=hi["metrics"]["load_v"]["rms"]
    target=(a+b)/2
    threshold=min(ok,key=lambda r:abs(r["metrics"]["load_v"]["rms"]-target))
    summary={"results":results,"dark_candidate_uA":lo["photocurrent_uA"],"light_candidate_uA":hi["photocurrent_uA"],"threshold_candidate_uA":threshold["photocurrent_uA"],"endpoint_load_rms":[a,b],"target_mid_rms":target}
else:
    summary={"results":results,"failure":"no successful simulations"}
Path(OUT/"stage3_scan_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
