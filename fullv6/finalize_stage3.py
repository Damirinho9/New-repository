import csv, json, math, os, shutil, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"stage3-final"
OUT.mkdir(parents=True,exist_ok=True)
BUILD=ROOT/"fullv6"/"build_stage3_sim.py"
NETS=["sens","u_ctrl","t1","t2","drv","g1","g2","l","sw"]

def call(args, log):
    p=subprocess.run(args,capture_output=True,text=True,encoding="utf-8",errors="replace")
    Path(log).write_text((p.stdout or "")+"\n--- STDERR ---\n"+(p.stderr or ""),encoding="utf-8")
    return p

def build_and_sim(label,uA,duration=0.40,rate=7000):
    iph=uA*1e-6
    p=call([sys.executable,str(BUILD),label,str(iph)],OUT/f"{label}_build.log")
    ms14=ROOT/"stage3-out"/f"7330744_PhotoRelay_V6_SIM_{label}.ms14"
    rec={"label":label,"photocurrent_uA":uA,"build_rc":p.returncode,"ms14":str(ms14)}
    if p.returncode!=0 or not ms14.exists():
        rec["failure"]="build"
        return rec
    csvdir=OUT/f"{label}_csv"
    q=call([sys.executable,"-m","multisimforge","sim",str(ms14),"--nets",",".join(NETS),
            "--tran",f"{duration},{rate}","--csv",str(csvdir)],OUT/f"{label}_sim.log")
    rec["sim_rc"]=q.returncode
    try:
        rec["sim_json"]=json.loads((q.stdout or "").strip())
    except Exception:
        rec["sim_stdout"]=(q.stdout or "")[-4000:]
    csvfile=csvdir/"tran.csv"
    if not csvfile.exists():
        rec["failure"]="no_csv"
        return rec
    all_rows=[]
    with csvfile.open(newline="",encoding="utf-8") as f:
        rd=csv.DictReader(f)
        for r in rd:
            try:
                all_rows.append({k:float(v) for k,v in r.items()})
            except Exception:
                continue
    rec["last_time_s"]=all_rows[-1]["time"] if all_rows else None
    if not all_rows or rec["last_time_s"] < duration*0.99:
        rec["failure"]="incomplete_transient"
        return rec
    rows=[r for r in all_rows if r["time"] >= duration*0.55]
    if not rows:
        rec["failure"]="no_tail"
        return rec
    def stats(vals):
        n=len(vals); mean=sum(vals)/n
        return {"mean":mean,"rms":math.sqrt(sum(x*x for x in vals)/n),
                "min":min(vals),"max":max(vals),"pp":max(vals)-min(vals)}
    metrics={n:stats([r[n] for r in rows]) for n in NETS}
    metrics["load_v"]=stats([r["l"]-r["sw"] for r in rows])
    metrics["points_tail"]=len(rows)
    rec["metrics"]=metrics
    return rec

coarse_uA=[0.0,0.25,0.5,0.75,1.0,1.25,1.5,1.75,2.0,2.25,2.5,3.0,4.0,5.0,6.0,7.0,8.0,10.0]
coarse=[]
for i,u in enumerate(coarse_uA):
    rec=build_and_sim(f"coarse_{i:02d}_{str(u).replace('.','p')}uA",u)
    coarse.append(rec)
    (OUT/"coarse_progress.json").write_text(json.dumps(coarse,ensure_ascii=False,indent=2),encoding="utf-8")

ok=[r for r in coarse if r.get("metrics")]
if len(ok)<3:
    raise SystemExit("Less than three successful real Multisim transient runs")

ok.sort(key=lambda r:r["photocurrent_uA"])
vals=[r["metrics"]["load_v"]["rms"] for r in ok]
span=max(vals)-min(vals)
# Require the load to actually respond. This gate prevents inventing a threshold from noise.
if span < 5.0:
    (OUT/"FAIL_no_switching.json").write_text(json.dumps({"span_Vrms":span,"coarse":ok},ensure_ascii=False,indent=2),encoding="utf-8")
    raise SystemExit(f"Full model ran, but load response span is only {span:.6g} Vrms; no real threshold proven")

# Locate the largest adjacent output transition and refine there.
pairs=[]
for a,b in zip(ok,ok[1:]):
    du=b["photocurrent_uA"]-a["photocurrent_uA"]
    dv=abs(b["metrics"]["load_v"]["rms"]-a["metrics"]["load_v"]["rms"])
    pairs.append((dv/max(du,1e-12),a,b))
_,pa,pb=max(pairs,key=lambda x:x[0])
lo,hi=pa["photocurrent_uA"],pb["photocurrent_uA"]
fine_uA=[lo+(hi-lo)*i/12 for i in range(13)]
fine=[]
for i,u in enumerate(fine_uA):
    rec=build_and_sim(f"fine_{i:02d}_{u:.6f}uA".replace(".","p"),u,duration=0.50,rate=9000)
    fine.append(rec)
    (OUT/"fine_progress.json").write_text(json.dumps(fine,ensure_ascii=False,indent=2),encoding="utf-8")
fine_ok=[r for r in fine if r.get("metrics")]
if len(fine_ok)<5:
    raise SystemExit("Fine sweep did not yield enough successful real transient runs")

# Physical labels: darkness = zero photocurrent, light = highest photocurrent.
dark=min(ok,key=lambda r:abs(r["photocurrent_uA"]-0.0))
light=max(ok,key=lambda r:r["photocurrent_uA"])
dark_y=dark["metrics"]["load_v"]["rms"]
light_y=light["metrics"]["load_v"]["rms"]
target=(dark_y+light_y)/2
threshold=min(fine_ok,key=lambda r:abs(r["metrics"]["load_v"]["rms"]-target))

selected={
 "DARK":{"photocurrent_uA":dark["photocurrent_uA"]},
 "THRESHOLD":{"photocurrent_uA":threshold["photocurrent_uA"]},
 "LIGHT":{"photocurrent_uA":light["photocurrent_uA"]},
}

# Rebuild and measure the exact selected states with a longer transient.
final={}
for state,info in selected.items():
    r=build_and_sim(state,info["photocurrent_uA"],duration=0.80,rate=12000)
    if not r.get("metrics"):
        raise SystemExit(f"{state} final simulation failed")
    src=Path(r["ms14"])
    dst=OUT/f"7330744_PhotoRelay_V6_{state}.ms14"
    shutil.copy2(src,dst)
    csvsrc=OUT/f"{state}_csv"/"tran.csv"
    if csvsrc.exists():
        shutil.copy2(csvsrc,OUT/f"{state}_transient.csv")
    r["final_ms14"]=str(dst)
    final[state]=r

summary={
 "criterion":"three modes selected only from real NI Multisim transient data; threshold is closest fine-sweep point to midpoint of DARK/LIGHT load RMS",
 "coarse_transition_interval_uA":[lo,hi],
 "coarse_load_span_Vrms":span,
 "target_mid_load_rms_V":target,
 "selected":final,
}
(OUT/"7330744_stage3_real_results.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")

# Human-readable values to paste into the report; all originate from the final transient CSV.
lines=["7330744 Variant 6 - REAL NI Multisim results",""]
for state in ("LIGHT","THRESHOLD","DARK"):
    r=final[state]; m=r["metrics"]
    lines += [
      f"{state}: I_PH = {r['photocurrent_uA']:.9g} uA",
      f"  SENS mean = {m['sens']['mean']:.9g} V; RMS = {m['sens']['rms']:.9g} V",
      f"  U_CTRL mean = {m['u_ctrl']['mean']:.9g} V",
      f"  DRV mean = {m['drv']['mean']:.9g} V",
      f"  SW RMS = {m['sw']['rms']:.9g} V",
      f"  LOAD RMS = {m['load_v']['rms']:.9g} V; min={m['load_v']['min']:.9g}; max={m['load_v']['max']:.9g}",
      ""
    ]
(OUT/"7330744_stage3_real_values.txt").write_text("\n".join(lines),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
