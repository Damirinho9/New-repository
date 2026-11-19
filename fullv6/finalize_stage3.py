import csv,json,math,os,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/"stage3-final"; OUT.mkdir(parents=True,exist_ok=True); BUILD=ROOT/"fullv6"/"build_stage3_sim.py"
NETS=["sens","u_ctrl","t1","t2","drv","g18","g25","l","sw","n_int","g12","vt3_r6","br_top"]
def run(label,u,dur=.2,rate=8000,cfg=None):
 env=os.environ.copy(); cfg=cfg or {}; env.update({k:str(v) for k,v in cfg.items()})
 p=subprocess.run([sys.executable,str(BUILD),label,str(u*1e-6)],capture_output=True,text=True,encoding="utf-8",errors="replace",env=env)
 (OUT/f"{label}_build.log").write_text((p.stdout or "")+"\n--- STDERR ---\n"+(p.stderr or ""),encoding="utf-8")
 safe=re.sub(r"[^A-Za-z0-9_-]+","p",label).strip("p") or "probe"
 fms=ROOT/"stage3-out"/f"7330744_PhotoRelay_V6_SIM_{safe}.ms14"; rec={"label":label,"photocurrent_uA":u,"cfg":cfg,"ms14":str(fms),"build_rc":p.returncode}
 if p.returncode or not fms.exists():rec["failure"]="build";return rec
 d=OUT/f"{label}_csv"; q=subprocess.run([sys.executable,"-m","multisimforge","sim",str(fms),"--nets",",".join(NETS),"--tran",f"{dur},{rate}","--csv",str(d)],capture_output=True,text=True,encoding="utf-8",errors="replace",env=env)
 (OUT/f"{label}_sim.log").write_text((q.stdout or "")+"\n--- STDERR ---\n"+(q.stderr or ""),encoding="utf-8"); rec["sim_rc"]=q.returncode
 try: rec["sim_json"]=json.loads((q.stdout or "").strip())
 except: pass
 cf=d/"tran.csv"
 if q.returncode or rec.get("sim_json",{}).get("status")!="PASS" or not cf.exists(): rec["failure"]="sim"; return rec
 rows=[]
 for x in csv.DictReader(open(cf,encoding="utf-8")):
  try: rows.append({k:float(v) for k,v in x.items()})
  except: pass
 rec["last_time"]=rows[-1]["time"] if rows else None
 if len(rows)<4 or rec["last_time"]<dur*.9: rec["failure"]="incomplete"; return rec
 end=rows[-1]["time"]; cycles=max(3,int(dur*.4*50)); tail=[x for x in rows if x["time"]>=end-cycles/50]; tt=[x["time"] for x in tail]; dt=[b-a for a,b in zip(tt,tt[1:])]; T=sum(dt)
 if T<=0: rec["failure"]="no_time_span"; return rec
 def st(v):
  return {"mean":sum((a+b)*d/2 for a,b,d in zip(v,v[1:],dt))/T,"rms":math.sqrt(sum((a*a+b*b)*d/2 for a,b,d in zip(v,v[1:],dt))/T),"min":min(v),"max":max(v)}
 m={n:st([x[n] for x in tail]) for n in NETS}; m["load_v"]=st([x["l"]-x["sw"] for x in tail]); m["gate1_v"]=st([x["g18"]-x["n_int"] for x in tail]); m["gate2_v"]=st([x["g25"]-x["sw"] for x in tail]); rec["metrics"]=m; return rec
def load(r):return r.get("metrics",{}).get("load_v",{}).get("rms",-1)
def save(n,o):(OUT/n).write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding="utf-8")
base={"CTRL_SUPPLY":0,"KP501_FLIP":0,"VT3_FLIP":0,"BRIDGE_MODE":"dc_bt","BRIDGE_SWAP":0,"VD20_SWAP":0,"KP501_VTO":1.5,"KP707_VTO":3.2,"SCR_VTH":2.5}
# Recheck OFF and ON with separated rails, including cathode-relative SCR signals.
def pair_valid(a,b):
    return bool(a.get("metrics") and b.get("metrics") and min(load(a),load(b))<=30 and max(load(a),load(b))>=170 and abs(load(a)-load(b))>=140)

def pair(label,c,a,b):
    x=run(label+"_0",0,.24,8000,dict(c,**a))
    y=run(label+"_1",0,.24,8000,dict(c,**b))
    return {"cfg":c,"a":x,"b":y,"pass":pair_valid(x,y),"span":abs(load(x)-load(y)) if x.get("metrics") and y.get("metrics") else None}

direct=[]
for v in (1.5,2.5):
    c=dict(base,SCR_VTH=v)
    direct.append(pair("a1_"+str(v),c,{},{"FORCE_GATE_MA":80}))
    save("diag_1_direct_scr.json",direct)
bridge=[]
for mode in ("dc_bt","dc_tb","ac_tb"):
    for pol in (0,1):
        c=dict(base,BRIDGE_MODE=mode,VD20_SWAP=pol)
        bridge.append(pair("a2_"+mode+"_"+str(pol),c,{},{"FORCE_BRIDGE_MA":80}))
        save("diag_2_bridge.json",bridge)
vt3=[]
for mode in ("dc_bt","dc_tb"):
    for flip in (0,1):
        c=dict(base,BRIDGE_MODE=mode,VT3_FLIP=flip)
        vt3.append(pair("a3_"+mode+"_"+str(flip),c,{"FORCE_T2_V":6},{"FORCE_T2_V":-6}))
        save("diag_3_vt3.json",vt3)

# Reverse photocurrent direction and deleting body diodes are not accepted as physical solutions.
mods=[]
for idx,(mode,flip,v3) in enumerate((m,k,v) for m in ("dc_bt","dc_tb") for k in (0,1) for v in (0,1)):
    c=dict(base,BRIDGE_MODE=mode,KP501_FLIP=flip,VT3_FLIP=v3,PHOTO_DIR=1,PHOTO_PATCH=0)
    d=run(f"full_{idx}_dark",0,1.0,8000,c)
    l=run(f"full_{idx}_light",8,1.0,8000,c)
    mods.append({"cfg":c,"dark":d,"light":l,"valid":pair_valid(d,l),"span":abs(load(l)-load(d)) if d.get("metrics") and l.get("metrics") else None})
    save("diag_4_photo_models.json",mods)
valid=[x for x in mods if x["valid"]]
if not valid:
    raise SystemExit("BLOCK_A4: no source-consistent autonomous OFF/ON proven; see separate rails diagnostics")
best=max(valid,key=lambda x:x["span"]);cfg=best["cfg"];save("selected_config.json",best)
us=[0,.25,.5,.75,1,1.5,2,3,4,6,8]; coarse=[run(f"coarse_{i:02d}",u,1.0,8000,cfg) for i,u in enumerate(us)];save("coarse_progress.json",coarse); ok=[r for r in coarse if r.get("metrics")]
pairs=[(abs(load(b)-load(a))/max(b["photocurrent_uA"]-a["photocurrent_uA"],1e-9),a,b) for a,b in zip(ok,ok[1:])];_,a,b=max(pairs,key=lambda x:x[0]);lo,hi=a["photocurrent_uA"],b["photocurrent_uA"]
fine=[run(f"fine_{i:02d}",lo+(hi-lo)*i/12,1.0,8000,cfg) for i in range(13)];save("fine_progress.json",fine);fine=[r for r in fine if r.get("metrics")]
dark=min(ok,key=lambda r:r["photocurrent_uA"]); light=max(ok,key=lambda r:r["photocurrent_uA"]); target=(load(dark)+load(light))/2;th=min(fine,key=lambda r:abs(load(r)-target)); chosen={"DARK":dark["photocurrent_uA"],"THRESHOLD":th["photocurrent_uA"],"LIGHT":light["photocurrent_uA"]}
final={}
for s,u in chosen.items():
 r=run(s,u,.4,10000,dict(cfg,ADD_SCOPE=1,STRICT_GEOMETRY=1))
 if not r.get("metrics"):raise SystemExit("BLOCK_A6 "+s)
 dst=OUT/f"7330744_PhotoRelay_V6_{s}.ms14";shutil.copy2(r["ms14"],dst); final[s]=r|{"final_ms14":str(dst)}
if not pair_valid(final["DARK"],final["LIGHT"]):raise SystemExit("BLOCK_A6 final OFF/ON mismatch")
lightu=max(chosen["LIGHT"],4); rph=max(1e6,24/(lightu*1e-6)); tr=run("TRANSIENT",0,.4,12000,dict(cfg,ADD_SCOPE=1,TRANSIENT_PHOTO=1,PHOTO_PULSE_R_OHM=rph,STRICT_GEOMETRY=1))
if not tr.get("metrics"):raise SystemExit("BLOCK_A7 transient")

# Check distinct cycle RMS during transition, not merely presence of CSV.
with (OUT/"TRANSIENT_csv"/"tran.csv").open(encoding="utf-8") as fh:
    rr=[{k:float(v) for k,v in row.items()} for row in csv.DictReader(fh)]
cycle=[]
for i in range(1,int(rr[-1]["time"]*50)):
    pts=[r for r in rr if i/50<=r["time"]<(i+1)/50]
    if len(pts)>10: cycle.append(math.sqrt(sum((r["l"]-r["sw"])**2 for r in pts)/len(pts)))
save("transient_cycle_rms.json",cycle)
if not cycle or min(cycle)>30 or max(cycle)<170 or max(cycle)-min(cycle)<140:raise SystemExit("BLOCK_A7 no demonstrated transition")
td=OUT/"7330744_PhotoRelay_V6_TRANSIENT.ms14";shutil.copy2(tr["ms14"],td);tr["final_ms14"]=str(td)
summary={"status":"PHASE_A_NUMERIC_PASS","selected_config":cfg,"transition_interval_uA":[lo,hi],"selected_uA":chosen,"selected":final,"transient":tr};save("7330744_stage3_real_results.json",summary)
lines=["7330744 Variant 6 - REAL NI Multisim values",""]
for s in ("LIGHT","THRESHOLD","DARK"):
 m=final[s]["metrics"];lines += [f"{s}: I_PH={final[s]['photocurrent_uA']:.6g} uA",f"SENS={m['sens']['mean']:.6g} V; T1={m['t1']['mean']:.6g} V; T2={m['t2']['mean']:.6g} V; DRV={m['drv']['mean']:.6g} V",f"G1-K RMS={m['gate1_v']['rms']:.6g} V; G2-K RMS={m['gate2_v']['rms']:.6g} V; SW RMS={m['sw']['rms']:.6g} V; LOAD RMS={m['load_v']['rms']:.6g} V",""]
(OUT/"7330744_stage3_real_values.txt").write_text("\n".join(lines),encoding="utf-8");print(json.dumps({"status":"PHASE_A_NUMERIC_PASS","selected_uA":chosen,"transition":[lo,hi]},ensure_ascii=False))
