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
g=[]
for v in (2.5,1.5,.8):
 r=run(f"diag_gate_{v}",0,.16,9000,dict(base,SCR_VTH=v,FORCE_GATE_MA=80));g.append(r)
save("diag_1_direct_scr.json",g); ok=[r for r in g if r.get("metrics") and load(r)>180]
if not ok:raise SystemExit("BLOCK_A1 direct SCR")
base["SCR_VTH"]=max(ok,key=load)["cfg"]["SCR_VTH"]
br=[]
for mode in ("dc_bt","dc_tb","ac_tb"):
 for ma in (30,80):
  r=run(f"diag_bridge_{mode}_{ma}",0,.16,9000,dict(base,BRIDGE_MODE=mode,FORCE_BRIDGE_MA=ma));br.append(r)
save("diag_2_bridge.json",br); ok=[r for r in br if r.get("metrics") and load(r)>180]
if not ok:raise SystemExit("BLOCK_A2 bridge")
pref=[r for r in ok if r["cfg"]["BRIDGE_MODE"]=="dc_bt"]; base["BRIDGE_MODE"]=max(pref or ok,key=load)["cfg"]["BRIDGE_MODE"]
v3=[]
for flip in (0,1):
 for vv in (-3,-6):
  r=run(f"diag_vt3_{flip}_{abs(vv)}",0,.18,9000,dict(base,VT3_FLIP=flip,FORCE_T2_V=vv));v3.append(r)
save("diag_3_vt3.json",v3);ok=[r for r in v3 if r.get("metrics") and load(r)>180]
if not ok:raise SystemExit("BLOCK_A3 VT3")
pref=[r for r in ok if int(r["cfg"]["VT3_FLIP"])==0];base["VT3_FLIP"]=max(pref or ok,key=load)["cfg"]["VT3_FLIP"]
mods=[]
for a in (1.0,1.5,2.0):
 for z in (2.0,3.2,4.0):
  c=dict(base,KP501_VTO=a,KP707_VTO=z); d=run(f"pm_{a}_{z}_d",0,.22,9000,c); l=run(f"pm_{a}_{z}_l",8,.22,9000,c)
  mods.append({"cfg":c,"dark":d,"light":l,"span":abs(load(l)-load(d)),"lo":min(load(d),load(l)),"hi":max(load(d),load(l))})
save("diag_4_photo_models.json",mods);valid=[x for x in mods if x["span"]>100 and x["lo"]<60 and x["hi"]>170]
if not valid:raise SystemExit("BLOCK_A4 full photo cascade")
best=max(valid,key=lambda x:x["span"]);cfg=best["cfg"];save("selected_config.json",best)
us=[0,.5,1,1.5,2,2.5,3,3.5,4,5,6,8]; coarse=[run(f"coarse_{i:02d}",u,.25,10000,cfg) for i,u in enumerate(us)];save("coarse_progress.json",coarse); ok=[r for r in coarse if r.get("metrics")]
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
