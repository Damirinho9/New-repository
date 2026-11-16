import csv, json, math, os, shutil, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"stage3-final"
OUT.mkdir(parents=True,exist_ok=True)
BUILD=ROOT/"fullv6"/"build_stage3_sim.py"
NETS=["sens","u_ctrl","t1","t2","drv","g18","g25","l","sw"]

def call(args, log):
    p=subprocess.run(args,capture_output=True,text=True,encoding="utf-8",errors="replace")
    Path(log).write_text((p.stdout or "")+"\n--- STDERR ---\n"+(p.stderr or ""),encoding="utf-8")
    return p

def build_and_sim(label,uA,duration=0.40,rate=7000,cfg=None):
    iph=uA*1e-6
    env=os.environ.copy()
    cfg=cfg or {}
    for k,v in cfg.items():
        env[k]=str(v)
    p=subprocess.run([sys.executable,str(BUILD),label,str(iph)],capture_output=True,text=True,encoding="utf-8",errors="replace",env=env)
    Path(OUT/f"{label}_build.log").write_text((p.stdout or "")+"\n--- STDERR ---\n"+(p.stderr or ""),encoding="utf-8")
    ms14=ROOT/"stage3-out"/f"7330744_PhotoRelay_V6_SIM_{label}.ms14"
    rec={"label":label,"photocurrent_uA":uA,"build_rc":p.returncode,"ms14":str(ms14)}
    if p.returncode!=0 or not ms14.exists():
        rec["failure"]="build"
        return rec
    csvdir=OUT/f"{label}_csv"
    q=subprocess.run([sys.executable,"-m","multisimforge","sim",str(ms14),"--nets",",".join(NETS),
            "--tran",f"{duration},{rate}","--csv",str(csvdir)],capture_output=True,text=True,encoding="utf-8",errors="replace",env=env)
    Path(OUT/f"{label}_sim.log").write_text((q.stdout or "")+"\n--- STDERR ---\n"+(q.stderr or ""),encoding="utf-8")
    rec["sim_rc"]=q.returncode
    try:
        rec["sim_json"]=json.loads((q.stdout or "").strip())
    except Exception:
        rec["sim_stdout"]=(q.stdout or "")[-4000:]
    csvfile=csvdir/"tran.csv"
    if not csvfile.exists():
        rec["failure"]="no_csv"
        return rec
    rows=[]
    with csvfile.open(newline="",encoding="utf-8") as f:
        rd=csv.DictReader(f)
        for r in rd:
            try:
                vals={k:float(v) for k,v in r.items()}
            except Exception:
                continue
            if vals["time"] >= duration*0.55:
                rows.append(vals)
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

# First determine the source-ambiguous pin assignments from real Multisim response.
# The source does not state MOSFET D/S or bridge +/- pins, so these are legitimate model choices.
candidates=[]
for kpflip in (0,1):
    for vt3flip in (0,1):
        for bswap in (0,1):
            cfg={"KP501_MODEL":"2N6659","KP501_FLIP":kpflip,"VT3_FLIP":vt3flip,"BRIDGE_SWAP":bswap,"VD20_SWAP":0}
            samples=[]
            for j,u in enumerate((0.0,15.0)):
                rec=build_and_sim(f"cfg_k{kpflip}_v{vt3flip}_b{bswap}_{j}",u,duration=0.22,rate=4500,cfg=cfg)
                samples.append(rec)
            good=[r for r in samples if r.get("metrics")]
            span=abs(good[-1]["metrics"]["load_v"]["rms"]-good[0]["metrics"]["load_v"]["rms"]) if len(good)==2 else -1.0
            candidates.append({"cfg":cfg,"samples":samples,"load_span_Vrms":span})
            (OUT/"candidate_progress.json").write_text(json.dumps(candidates,ensure_ascii=False,indent=2),encoding="utf-8")

selected_candidate=max(candidates,key=lambda x:x["load_span_Vrms"])
selected_cfg=selected_candidate["cfg"]
(OUT/"selected_config.json").write_text(json.dumps(selected_candidate,ensure_ascii=False,indent=2),encoding="utf-8")
if selected_candidate["load_span_Vrms"] < 10.0:
    # One extra source-ambiguous test: reverse the unmarked VD20 polarity using the best D/S + bridge mapping.
    alt=dict(selected_cfg); alt["VD20_SWAP"]=1
    samples=[build_and_sim(f"cfg_vd20swap_{j}",u,duration=0.22,rate=4500,cfg=alt) for j,u in enumerate((0.0,15.0))]
    good=[r for r in samples if r.get("metrics")]
    span=abs(good[-1]["metrics"]["load_v"]["rms"]-good[0]["metrics"]["load_v"]["rms"]) if len(good)==2 else -1.0
    candidates.append({"cfg":alt,"samples":samples,"load_span_Vrms":span})
    if span > selected_candidate["load_span_Vrms"]:
        selected_candidate=candidates[-1]; selected_cfg=alt
        (OUT/"selected_config.json").write_text(json.dumps(selected_candidate,ensure_ascii=False,indent=2),encoding="utf-8")

coarse_uA=[0.0,2.0,5.0,8.0,10.0,12.0,15.0,20.0,25.0]
coarse=[]
for i,u in enumerate(coarse_uA):
    rec=build_and_sim(f"coarse_{i:02d}_{str(u).replace('.','p')}uA",u,duration=0.30,rate=6000,cfg=selected_cfg)
    coarse.append(rec)
    (OUT/"coarse_progress.json").write_text(json.dumps(coarse,ensure_ascii=False,indent=2),encoding="utf-8")

ok=[r for r in coarse if r.get("metrics")]
if len(ok)<3:
    raise SystemExit("Less than three successful real Multisim transient runs")
ok.sort(key=lambda r:r["photocurrent_uA"])
vals=[r["metrics"]["load_v"]["rms"] for r in ok]
span=max(vals)-min(vals)
# Require the load to actually respond. This gate prevents inventing a threshold from noise.
if span < 30.0:
    (OUT/"FAIL_no_switching.json").write_text(json.dumps({"span_Vrms":span,"coarse":ok},ensure_ascii=False,indent=2),encoding="utf-8")
    raise SystemExit(f"Full model ran, but load response span is only {span:.6g} Vrms; no clear real switching threshold proven")

# Locate the largest adjacent output transition and refine there.
pairs=[]
for a,b in zip(ok,ok[1:]):
    du=b["photocurrent_uA"]-a["photocurrent_uA"]
    dv=abs(b["metrics"]["load_v"]["rms"]-a["metrics"]["load_v"]["rms"])
    pairs.append((dv/max(du,1e-12),a,b))
_,pa,pb=max(pairs,key=lambda x:x[0])
lo,hi=pa["photocurrent_uA"],pb["photocurrent_uA"]
fine_uA=[lo+(hi-lo)*i/8 for i in range(9)]
fine=[]
for i,u in enumerate(fine_uA):
    rec=build_and_sim(f"fine_{i:02d}_{u:.6f}uA".replace(".","p"),u,duration=0.35,rate=7000,cfg=selected_cfg)
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
    r=build_and_sim(state,info["photocurrent_uA"],duration=0.50,rate=9000,cfg=selected_cfg)
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
 "selected_source_ambiguous_pin_assignment":selected_cfg,
 "candidate_load_spans_Vrms":[{"cfg":x["cfg"],"span":x["load_span_Vrms"]} for x in candidates],
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
