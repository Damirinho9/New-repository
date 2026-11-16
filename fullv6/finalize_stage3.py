import csv, json, math, os, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"stage3-final"; OUT.mkdir(parents=True,exist_ok=True)
BUILD=ROOT/"fullv6"/"build_stage3_sim.py"
NETS=["sens","u_ctrl","t1","t2","drv","g18","g25","l","sw"]

def build_and_sim(label,uA,duration=0.30,rate=6000,cfg=None):
    env=os.environ.copy(); cfg=cfg or {}; env.update({k:str(v) for k,v in cfg.items()})
    p=subprocess.run([sys.executable,str(BUILD),label,str(uA*1e-6)],capture_output=True,text=True,encoding="utf-8",errors="replace",env=env)
    (OUT/f"{label}_build.log").write_text((p.stdout or "")+"\n--- STDERR ---\n"+(p.stderr or ""),encoding="utf-8")
    ms14=ROOT/"stage3-out"/f"7330744_PhotoRelay_V6_SIM_{label}.ms14"
    rec={"label":label,"photocurrent_uA":uA,"build_rc":p.returncode,"ms14":str(ms14),"cfg":cfg}
    if p.returncode or not ms14.exists(): rec["failure"]="build"; return rec
    csvdir=OUT/f"{label}_csv"
    q=subprocess.run([sys.executable,"-m","multisimforge","sim",str(ms14),"--nets",",".join(NETS),"--tran",f"{duration},{rate}","--csv",str(csvdir)],capture_output=True,text=True,encoding="utf-8",errors="replace",env=env)
    (OUT/f"{label}_sim.log").write_text((q.stdout or "")+"\n--- STDERR ---\n"+(q.stderr or ""),encoding="utf-8")
    rec["sim_rc"]=q.returncode
    try: rec["sim_json"]=json.loads((q.stdout or "").strip())
    except Exception: rec["sim_stdout"]=(q.stdout or "")[-4000:]
    f=csvdir/"tran.csv"
    if q.returncode or rec.get("sim_json",{}).get("failures") or not f.exists(): rec["failure"]="simulation_error"; return rec
    rows=[]
    with f.open(newline="",encoding="utf-8") as h:
        for r in csv.DictReader(h):
            try: v={k:float(x) for k,x in r.items()}
            except Exception: continue
            if v["time"]>=duration*0.55: rows.append(v)
    if len(rows)<3 or rows[-1]["time"]<duration*0.95: rec["failure"]="no_tail"; return rec
    tt=[r["time"] for r in rows]; dt=[b-a for a,b in zip(tt,tt[1:])]; span=sum(dt)
    def stats(vals):
        mean=sum((a+b)*d/2 for a,b,d in zip(vals,vals[1:],dt))/span
        rms=math.sqrt(sum((a*a+b*b)*d/2 for a,b,d in zip(vals,vals[1:],dt))/span)
        return {"mean":mean,"rms":rms,"min":min(vals),"max":max(vals),"pp":max(vals)-min(vals)}
    m={n:stats([r[n] for r in rows]) for n in NETS}
    m["load_v"]=stats([r["l"]-r["sw"] for r in rows])
    m["gate1_v"]=stats([r["g18"] for r in rows])
    m["gate2_v"]=stats([r["g25"]-r["sw"] for r in rows])
    rec["metrics"]=m; return rec

configs=[
 {"CTRL_SUPPLY":0,"KP501_FLIP":0,"VT3_FLIP":1,"BRIDGE_MODE":"ac_tb","BRIDGE_SWAP":0,"VD20_SWAP":0},
 {"CTRL_SUPPLY":1,"KP501_FLIP":0,"VT3_FLIP":1,"BRIDGE_MODE":"ac_tb","BRIDGE_SWAP":0,"VD20_SWAP":0},
 {"CTRL_SUPPLY":1,"KP501_FLIP":0,"VT3_FLIP":1,"BRIDGE_MODE":"ac_tb","BRIDGE_SWAP":1,"VD20_SWAP":0},
 {"CTRL_SUPPLY":1,"KP501_FLIP":0,"VT3_FLIP":0,"BRIDGE_MODE":"ac_tb","BRIDGE_SWAP":0,"VD20_SWAP":0},
 {"CTRL_SUPPLY":1,"KP501_FLIP":1,"VT3_FLIP":1,"BRIDGE_MODE":"ac_tb","BRIDGE_SWAP":0,"VD20_SWAP":0},
]
candidates=[]
for i,cfg in enumerate(configs):
    samples=[build_and_sim(f"cfg{i}_{j}",u,0.22,4500,cfg) for j,u in enumerate((0.0,5000.0))]
    good=[r for r in samples if r.get("metrics")]
    if len(good)==2:
        y=[r["metrics"]["load_v"]["rms"] for r in good]; span=abs(y[1]-y[0])
        score=span-(50 if min(y)>60 else 0)-(50 if max(y)<150 else 0)
    else: span=-1; score=-999
    candidates.append({"cfg":cfg,"samples":samples,"load_span_Vrms":span,"score":score})
    (OUT/"candidate_progress.json").write_text(json.dumps(candidates,ensure_ascii=False,indent=2),encoding="utf-8")
best=max(candidates,key=lambda x:x["score"]); cfg=best["cfg"]
(OUT/"selected_config.json").write_text(json.dumps(best,ensure_ascii=False,indent=2),encoding="utf-8")

coarse_uA=[0,25,50,100,200,500,1000,2000,3500,5000]
coarse=[build_and_sim(f"coarse_{i:02d}",float(u),0.28,6000,cfg) for i,u in enumerate(coarse_uA)]
(OUT/"coarse_progress.json").write_text(json.dumps(coarse,ensure_ascii=False,indent=2),encoding="utf-8")
ok=[r for r in coarse if r.get("metrics")]
if len(ok)<5: raise SystemExit("Insufficient successful transient points")
vals=[r["metrics"]["load_v"]["rms"] for r in ok]; total=max(vals)-min(vals)
if total<80:
    (OUT/"FAIL_no_switching.json").write_text(json.dumps({"span_Vrms":total,"coarse":ok,"candidates":candidates},ensure_ascii=False,indent=2),encoding="utf-8")
    raise SystemExit(f"No clear load switching: span={total:.6g} Vrms")

pairs=[]
for a,b in zip(ok,ok[1:]):
    du=b["photocurrent_uA"]-a["photocurrent_uA"]; dy=abs(b["metrics"]["load_v"]["rms"]-a["metrics"]["load_v"]["rms"])
    pairs.append((dy/max(du,1e-12),a,b))
_,a,b=max(pairs,key=lambda x:x[0]); lo=a["photocurrent_uA"]; hi=b["photocurrent_uA"]
fine_uA=[lo+(hi-lo)*i/8 for i in range(9)]
fine=[build_and_sim(f"fine_{i:02d}",u,0.32,7000,cfg) for i,u in enumerate(fine_uA)]
(OUT/"fine_progress.json").write_text(json.dumps(fine,ensure_ascii=False,indent=2),encoding="utf-8")
fine=[r for r in fine if r.get("metrics")]
dark=min(ok,key=lambda r:r["photocurrent_uA"]); light=max(ok,key=lambda r:r["photocurrent_uA"])
target=(dark["metrics"]["load_v"]["rms"]+light["metrics"]["load_v"]["rms"])/2
thr=min(fine,key=lambda r:abs(r["metrics"]["load_v"]["rms"]-target))
chosen={"DARK":dark["photocurrent_uA"],"THRESHOLD":thr["photocurrent_uA"],"LIGHT":light["photocurrent_uA"]}

final={}
for state,u in chosen.items():
    c=dict(cfg); c["ADD_SCOPE"]=1
    r=build_and_sim(state,u,0.50,9000,c)
    if not r.get("metrics"): raise SystemExit(f"{state} final failed")
    src=Path(r["ms14"]); dst=OUT/f"7330744_PhotoRelay_V6_{state}.ms14"; shutil.copy2(src,dst)
    csvsrc=OUT/f"{state}_csv"/"tran.csv"
    if csvsrc.exists(): shutil.copy2(csvsrc,OUT/f"{state}_transient.csv")
    r["final_ms14"]=str(dst); final[state]=r
summary={"selected_config":cfg,"candidate_results":candidates,"coarse_load_span_Vrms":total,"transition_interval_uA":[lo,hi],"selected":final}
(OUT/"7330744_stage3_real_results.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
lines=["7330744 Variant 6 - REAL NI Multisim transient values",""]
for state in ("LIGHT","THRESHOLD","DARK"):
    r=final[state]; m=r["metrics"]
    lines += [f"{state}: I_PH={r['photocurrent_uA']:.6g} uA",f" SENS mean={m['sens']['mean']:.6g} V",f" U_CTRL mean={m['u_ctrl']['mean']:.6g} V",f" DRV mean={m['drv']['mean']:.6g} V",f" G1-K RMS={m['gate1_v']['rms']:.6g} V",f" G2-K RMS={m['gate2_v']['rms']:.6g} V",f" LOAD RMS={m['load_v']['rms']:.6g} V",""]
(OUT/"7330744_stage3_real_values.txt").write_text("\n".join(lines),encoding="utf-8")
print(json.dumps(summary,ensure_ascii=False,indent=2))
