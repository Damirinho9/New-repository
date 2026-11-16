import csv, json, math, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"model2-quick"
OUT.mkdir(parents=True,exist_ok=True)
BUILD=ROOT/"fullv6"/"build_stage3_sim.py"
NETS=["sens","u_ctrl","t1","t2","drv","g1","g2","l","sw"]

def run(cmd,log):
    p=subprocess.run(cmd,capture_output=True,text=True,encoding="utf-8",errors="replace")
    Path(log).write_text((p.stdout or "")+"\n--- STDERR ---\n"+(p.stderr or ""),encoding="utf-8")
    return p

def stats(vals):
    n=len(vals); mean=sum(vals)/n
    return {"mean":mean,"rms":math.sqrt(sum(v*v for v in vals)/n),"min":min(vals),"max":max(vals),"pp":max(vals)-min(vals)}

res=[]
for uA in [0.0,3.0,4.0,5.0]:
    label=f"Q_{str(uA).replace('.','p')}uA"
    b=run([sys.executable,str(BUILD),label,str(uA*1e-6)],OUT/f"{label}_build.txt")
    ms14=ROOT/"stage3-out"/f"7330744_PhotoRelay_V6_SIM_{label}.ms14"
    r={"uA":uA,"build_rc":b.returncode,"ms14":str(ms14)}
    if b.returncode!=0 or not ms14.exists():
        r["failure"]="build"; res.append(r); continue
    csvdir=OUT/f"{label}_csv"
    s=run([sys.executable,"-m","multisimforge","sim",str(ms14),"--nets",",".join(NETS),"--tran","0.4,8000","--csv",str(csvdir)],OUT/f"{label}_sim.txt")
    r["sim_rc"]=s.returncode
    try:r["sim_json"]=json.loads((s.stdout or "").strip())
    except Exception:r["sim_stdout"]=(s.stdout or "")[-3000:]
    f=csvdir/"tran.csv"
    if not f.exists():
        r["failure"]="no_csv"; res.append(r); continue
    with f.open(newline="",encoding="utf-8") as fh:
        rows=[{k:float(v) for k,v in x.items()} for x in csv.DictReader(fh)]
    r["points"]=len(rows); r["last_time_s"]=rows[-1]["time"] if rows else None
    if not rows or r["last_time_s"]<0.396:
        r["failure"]="incomplete_transient"; res.append(r); continue
    tail=[x for x in rows if x["time"]>=0.22]
    m={n:stats([x[n] for x in tail]) for n in NETS}
    m["load_v"]=stats([x["l"]-x["sw"] for x in tail])
    r["metrics"]=m
    res.append(r)
(OUT/"quick_results.json").write_text(json.dumps(res,ensure_ascii=False,indent=2),encoding="utf-8")
ok=[r for r in res if r.get("metrics")]
if len(ok)!=4:
    raise SystemExit("not all four native ZVN2106A diagnostic transients completed")
span=max(r["metrics"]["load_v"]["rms"] for r in ok)-min(r["metrics"]["load_v"]["rms"] for r in ok)
print(json.dumps({"results":res,"load_rms_span_V":span},ensure_ascii=False,indent=2))
if span<5:
    raise SystemExit(f"model2 full-duration load span too small: {span}")
