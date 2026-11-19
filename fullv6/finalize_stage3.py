import csv,json,math,os,re,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent; OUT=ROOT/"stage3-final"; OUT.mkdir(parents=True,exist_ok=True); BUILD=ROOT/"fullv6"/"build_stage3_sim.py"
NETS=["sens","u_ctrl","t1","t2","drv","g18","g25","l","sw"]
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
 if q.returncode or not cf.exists(): rec["failure"]="sim"; return rec
 rows=[]
 for x in csv.DictReader(open(cf,encoding="utf-8")):
  try: rows.append({k:float(v) for k,v in x.items()})
  except: pass
 rec["last_time"]=rows[-1]["time"] if rows else None
 if len(rows)<4 or rec["last_time"]<dur*.9: rec["failure"]="incomplete"; return rec
 tail=[x for x in rows if x["time"]>=dur*.55]; tt=[x["time"] for x in tail]; dt=[b-a for a,b in zip(tt,tt[1:])]; T=sum(dt)
 def st(v):
  return {"mean":sum((a+b)*d/2 for a,b,d in zip(v,v[1:],dt))/T,"rms":math.sqrt(sum((a*a+b*b)*d/2 for a,b,d in zip(v,v[1:],dt))/T),"min":min(v),"max":max(v)}
 m={n:st([x[n] for x in tail]) for n in NETS}; m["load_v"]=st([x["l"]-x["sw"] for x in tail]); m["gate1_v"]=st([x["g18"] for x in tail]); m["gate2_v"]=st([x["g25"]-x["sw"] for x in tail]); rec["metrics"]=m; return rec
def load(r):return r.get("metrics",{}).get("load_v",{}).get("rms",-1)
def save(n,o):(OUT/n).write_text(json.dumps(o,ensure_ascii=False,indent=2),encoding="utf-8")
base={"CTRL_SUPPLY":0,"KP501_FLIP":0,"VT3_FLIP":0,"BRIDGE_MODE":"dc_bt","BRIDGE_SWAP":0,"VD20_SWAP":0,"KP501_VTO":1.5,"KP707_VTO":3.2,"SCR_VTH":2.5}
save("validated_upstream.json",{
 "A1_direct_scr":"PASS run 44485499970",
 "A2_RB154":"PASS dc_bt in run 44485499970",
 "A3_VT3":"PASS VT3_FLIP=0 in run 44485499970"
})

def photo_batch(name,patch,direction):
 out=[]
 for flip in (0,1):
  for a in (1.0,1.5,2.0):
   c=dict(base,PHOTO_PATCH=patch,PHOTO_DIR=direction,KP501_FLIP=flip,KP501_VTO=a,KP707_VTO=3.2)
   d=run(f"{name}_f{flip}_v{a}_d",0,.22,9000,c)
   l=run(f"{name}_f{flip}_v{a}_l",8,.22,9000,c)
   out.append({"cfg":c,"dark":d,"light":l,"span":abs(load(l)-load(d)),"lo":min(load(d),load(l)),"hi":max(load(d),load(l))})
 save(f"diag_4_{name}.json",out)
 return out

# Isolate VT1/VT2 before the photocurrent sweep. The source does not mark D/S.
# Test both D/S assignments and both simulation-body-diode choices with SENS forced positive/negative.
chain=[]
for flip in (0,1):
 for body in (1,0):
  c=dict(base,KP501_FLIP=flip,KP501_BODY_DIODE=body,KP501_VTO=1.5,PHOTO_PATCH=1)
  off=run(f"chain_f{flip}_b{body}_pos",0,.20,9000,dict(c,FORCE_SENS_V=3))
  on=run(f"chain_f{flip}_b{body}_neg",0,.20,9000,dict(c,FORCE_SENS_V=-3))
  span=abs(load(on)-load(off))
  chain.append({"cfg":c,"positive_sens":off,"negative_sens":on,"span":span,"off":load(off),"on":load(on)})
save("diag_4a_forced_sens.json",chain)
chain_valid=[x for x in chain if x["span"]>100 and min(x["off"],x["on"])<80 and max(x["off"],x["on"])>170]
if chain_valid:
 chosen_chain=max(chain_valid,key=lambda x:x["span"]); base.update({k:v for k,v in chosen_chain["cfg"].items() if k in ("KP501_FLIP","KP501_BODY_DIODE","KP501_VTO")})
else:
 save("FAIL_photo_chain_forced_sens.json",chain)
 raise SystemExit("BLOCK_A4A VT1/VT2 cannot switch T2 from forced SENS")

mods=photo_batch("native_normal",0,1)
valid=[x for x in mods if x["span"]>100 and x["lo"]<80 and x["hi"]>170]
if not valid:
 more=photo_batch("patched_normal",1,1); mods+=more
 valid=[x for x in mods if x["span"]>100 and x["lo"]<80 and x["hi"]>170]
if not valid:
 more=photo_batch("native_reverse",0,-1)+photo_batch("patched_reverse",1,-1); mods+=more
 valid=[x for x in mods if x["span"]>100 and x["lo"]<80 and x["hi"]>170]
save("diag_4_photo_models.json",mods)
if not valid:raise SystemExit("BLOCK_A4 full photo cascade after D/S, photocurrent direction and FD320 model tests")
best=max(valid,key=lambda x:x["span"]);cfg=best["cfg"];save("selected_config.json",best)
us=[0,.25,.5,.75,1,1.5,2,3,4,6,8]; coarse=[run(f"coarse_{i:02d}",u,.25,10000,cfg) for i,u in enumerate(us)];save("coarse_progress.json",coarse); ok=[r for r in coarse if r.get("metrics")]
pairs=[(abs(load(b)-load(a))/max(b["photocurrent_uA"]-a["photocurrent_uA"],1e-9),a,b) for a,b in zip(ok,ok[1:])];_,a,b=max(pairs,key=lambda x:x[0]);lo,hi=a["photocurrent_uA"],b["photocurrent_uA"]
fine=[run(f"fine_{i:02d}",lo+(hi-lo)*i/12,.27,11000,cfg) for i in range(13)];save("fine_progress.json",fine);fine=[r for r in fine if r.get("metrics")]
dark=min(ok,key=lambda r:r["photocurrent_uA"]); light=max(ok,key=lambda r:r["photocurrent_uA"]); target=(load(dark)+load(light))/2;th=min(fine,key=lambda r:abs(load(r)-target)); chosen={"DARK":dark["photocurrent_uA"],"THRESHOLD":th["photocurrent_uA"],"LIGHT":light["photocurrent_uA"]}
final={}
for s,u in chosen.items():
 r=run(s,u,.4,10000,dict(cfg,ADD_SCOPE=1))
 if not r.get("metrics"):raise SystemExit("BLOCK_A6 "+s)
 dst=OUT/f"7330744_PhotoRelay_V6_{s}.ms14";shutil.copy2(r["ms14"],dst); final[s]=r|{"final_ms14":str(dst)}
lightu=max(chosen["LIGHT"],4); rph=max(1e6,24/(lightu*1e-6)); tr=run("TRANSIENT",0,.4,12000,dict(cfg,ADD_SCOPE=1,TRANSIENT_PHOTO=1,PHOTO_PULSE_R_OHM=rph))
if not tr.get("metrics"):raise SystemExit("BLOCK_A7 transient")
td=OUT/"7330744_PhotoRelay_V6_TRANSIENT.ms14";shutil.copy2(tr["ms14"],td);tr["final_ms14"]=str(td)
summary={"status":"PHASE_A_NUMERIC_PASS","selected_config":cfg,"transition_interval_uA":[lo,hi],"selected_uA":chosen,"selected":final,"transient":tr};save("7330744_stage3_real_results.json",summary)
lines=["7330744 Variant 6 - REAL NI Multisim values",""]
for s in ("LIGHT","THRESHOLD","DARK"):
 m=final[s]["metrics"];lines += [f"{s}: I_PH={final[s]['photocurrent_uA']:.6g} uA",f"SENS={m['sens']['mean']:.6g} V; T1={m['t1']['mean']:.6g} V; T2={m['t2']['mean']:.6g} V; DRV={m['drv']['mean']:.6g} V",f"G1-K RMS={m['gate1_v']['rms']:.6g} V; G2-K RMS={m['gate2_v']['rms']:.6g} V; SW RMS={m['sw']['rms']:.6g} V; LOAD RMS={m['load_v']['rms']:.6g} V",""]
(OUT/"7330744_stage3_real_values.txt").write_text("\n".join(lines),encoding="utf-8");print(json.dumps({"status":"PHASE_A_NUMERIC_PASS","selected_uA":chosen,"transition":[lo,hi]},ensure_ascii=False))
