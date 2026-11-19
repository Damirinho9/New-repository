"""Stage 4: search only datasheet-supported KP501A corners and source-ambiguous D/S/bridge assignments.
Acceptance is based on native NI Multisim LOAD RMS, never SENS alone.
"""
import csv,json,math,os,subprocess,sys,traceback,hashlib
from pathlib import Path
import numpy as np
from multisimforge import builder,check,xmlio
from multisimforge.parts import Library
from topology_models import patch_models,verify_saved_cards
OUT=Path("stage4-out");OUT.mkdir(exist_ok=True)
LIB=Library()
ALL={}
def save(n,o):(OUT/n).write_text(json.dumps(o,indent=2,ensure_ascii=False),encoding="utf-8")
def X(r,m,**p):return "X"+r+" "+m+" "+" ".join(f"{k}={v}" for k,v in p.items())
def fet(r,m,a,b,g,flip):return X(r,m,D=a if flip else b,G=g,S=b if flip else a)
def bridge(mode):
    p={"dc_tb":{"V+":"br_top","V-":"0","AC1":"g18","AC2":"g25"},
       "dc_bt":{"V+":"0","V-":"br_top","AC1":"g18","AC2":"g25"}}[mode]
    return X("VD6","MDA2504",**p)
def power(mode,df):
    return [X("VS1","SCR",A="sw",K="n_int",G="g18"),"R8 g18 n_int 56",
      X("VD4","MUR1510G",A="g18" if df else "n_int",K="n_int" if df else "g18"),
      "RMON drv drvmon 1","XFU1 drvmon br_top 30_AMP",bridge(mode),
      X("VD5","MUR1510G",A="sw",K="g25"),"R9 g25 sw 56",X("VS2","SCR",A="n_int",K="sw",G="g25"),
      "C3 l n_int 47n CAPACITOR_VIRTUAL","XFU2 n_int n 30_AMP","RREF n_int 0 1G",
      "V1 ac_src n SIN(0 311.1269837 50)","RLINE ac_src l 10","RLOAD l sw 1k"]
def control(flip):return [fet("VT3","IRFD110","t2","vt3_r6","0",flip),"R6 vt3_r6 drv 51","RU1 drv 0 10meg"]
def source():return [X("HL1","LED_red",A="led_a",K="u_ctrl"),X("VD3","MUR1510G",A="led_r",K="led_a"),"R7 led_r l 58k",X("XP1","HDR1X5",P1="sw",P2="l",P3="l",P4="n",P5="nc_xp1")]
def photo(f2,iph,bench=False):
    n=["R1 u_ctrl n_r1 4.7meg","R2 n_r1 sens 47k",X("VD1","PHOTO_DIODE_RATED",A="0",K="sens"),
       "C1 sens 0 470n CAP_ELECTROLIT_VIRTUAL","C2 u_ctrl 0 100n CAPACITOR_VIRTUAL",
       fet("VT1","2N6659","sens","t1","g12",False),"R3 g12 0 330","R4 u_ctrl t1 10k",
       fet("VT2","2N6659","t1","t2","g12",f2),X("VD2","1N4742A",A="0",K="u_ctrl"),"R5 u_ctrl t2 5.1k",
       f"I1 sens 0 {iph*1e-6:.12g}"]
    if bench:n+=["VTEST u_ctrl 0 12"]
    return n
PWR=["drv","drvmon","br_top","g18","g25","n_int","sw","l","ac_src","n"]
PH=["sens","t1","t2","u_ctrl","g12"]
def stat(t,y,a,b):
    m=(t>a)&(t<b);tt=np.r_[a,t[m],b];yy=np.interp(tt,t,y);d=b-a
    return {"mean":float(np.trapezoid(yy,tt)/d),"rms":float(np.sqrt(np.trapezoid(yy*yy,tt)/d)),"min":float(yy.min()),"max":float(yy.max())}
def run(name,net,nets,dur,vto):
    rec={"name":name,"KP501_VTO":vto};ALL[name]=rec
    f=OUT/(name+".ms14");(OUT/(name+".net")).write_text("\n".join(net)+"\n",encoding="utf-8")
    old=os.environ.get("KP501_CORNER_VTO")
    try:
        os.environ["KP501_CORNER_VTO"]=str(vto)
        spec={"netlist":"\n".join(net)+"\n","output":str(f),"net_names":True,"sheet":[21,11],
              "sim_time":str(int(dur*1000))+"ms","layout":{"GND":[[108,756],[540,756],[972,756],[1404,756],[1836,756]]}}
        builder.build(spec,lib=LIB,allow_fallback=True,auto_repair=True,repair_budget_s=10)
        root=xmlio.load(f);refs={z.split()[0][1:] for z in net if z.startswith("X")}&{"VT1","VT2","VT3","VS1","VS2","VD3","VD4","VD5"}
        rec["model_notes"]=patch_models(root,xmlio,refs);xmlio.save(root,f,compress=True);verify_saved_cards(xmlio.load(f),xmlio,refs)
        rec["sha256"]=hashlib.sha256(f.read_bytes()).hexdigest();rec["pinmap"]=check.inspect(f)["nets"]
        dest=OUT/(name+"_csv")
        p=subprocess.run([sys.executable,"-m","multisimforge","sim",str(f.resolve()),"--nets",",".join(nets),"--tran",f"{dur},8000","--csv",str(dest.resolve())],
                         capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=125)
        (OUT/(name+"_sim.log")).write_text(p.stdout+"\n"+p.stderr,encoding="utf-8")
        j=json.loads(p.stdout)
        if p.returncode or j.get("status") not in ("PASS","WARN") or j.get("failures") or j.get("missing"):raise RuntimeError("native sim "+repr(j))
        rows=list(csv.DictReader((dest/"tran.csv").open(encoding="utf-8-sig")));t=np.array([float(r["time"]) for r in rows])
        d={n:np.array([float(r[n]) for r in rows]) for n in nets}
        if t[-1]<dur*.95 or len(t)<100:raise RuntimeError("incomplete transient")
        a=t[-1]-.08;b=t[-1]
        if "l" in d:
            d["load"]=d["l"]-d["sw"];d["gk1"]=d["g18"]-d["n_int"];d["gk2"]=d["g25"]-d["sw"];d["drive_i"]=d["drv"]-d["drvmon"]
        rec["metrics"]={k:stat(t,v,a,b) for k,v in d.items()};rec["status"]="MEASURED"
    except Exception as e:
        rec["status"]="FAIL";rec["error"]=repr(e);(OUT/(name+"_error.txt")).write_text(traceback.format_exc(),encoding="utf-8")
    finally:
        if old is None:os.environ.pop("KP501_CORNER_VTO",None)
        else:os.environ["KP501_CORNER_VTO"]=old
    save("all.json",ALL);print(name,rec["status"],rec.get("metrics",{}).get("t2",{}).get("mean"),rec.get("metrics",{}).get("load",{}).get("rms"),flush=True)
    return rec
def val(r,n,k="mean"):return r.get("metrics",{}).get(n,{}).get(k)
def load(r):return val(r,"load","rms")
def load_pair(a,b):
    if load(a) is None or load(b) is None:return False
    lo,hi=sorted([load(a),load(b)])
    return lo<=30 and hi>=170 and hi-lo>=140
# 1) Sensor-only: use exact source orientation for VT1 (S=SENS), both ambiguous VT2 orientations,
# and datasheet-supported low/nominal KP501A threshold corners. No power stage is present.
photos=[]
for vto in (1.0,1.2,1.5):
  for f2 in (False,True):
    dark=run(f"photo_v{str(vto).replace('.','p')}_f{int(f2)}_0u",photo(f2,0,True),PH,3.0,vto)
    light=run(f"photo_v{str(vto).replace('.','p')}_f{int(f2)}_16u",photo(f2,16,True),PH,3.0,vto)
    rec={"vto":vto,"f2":f2,"dark":dark["name"],"light":light["name"],"t2_dark":val(dark,"t2"),"t2_light":val(light,"t2")}
    rec["t2_span"]=abs(rec["t2_dark"]-rec["t2_light"]) if None not in (rec["t2_dark"],rec["t2_light"]) else -1
    photos.append(rec);save("PHOTO_CORNERS.json",photos)
photos=sorted([x for x in photos if x["t2_span"]>=0],key=lambda x:x["t2_span"],reverse=True)
# 2) Full native source graph: prioritize VT3 reverse D/S, because real dark T2 is ~+12 V rather than the old artificial +6 V.
endpoints=[]
for pc in photos[:3]:
  for mode in ("dc_tb","dc_bt"):
   for df in (False,True):
    for vf in (True,False):
      base=power(mode,df)+control(vf)+source()
      a=run(f"full_v{str(pc['vto']).replace('.','p')}_f{int(pc['f2'])}_{mode}_d{int(df)}_v{int(vf)}_0u",
            base+photo(pc["f2"],0,False),PWR+PH+["vt3_r6"],3.0,pc["vto"])
      b=run(f"full_v{str(pc['vto']).replace('.','p')}_f{int(pc['f2'])}_{mode}_d{int(df)}_v{int(vf)}_16u",
            base+photo(pc["f2"],16,False),PWR+PH+["vt3_r6"],3.0,pc["vto"])
      rec={"photo":pc,"mode":mode,"diode_flip":df,"vt3_flip":vf,"dark":a["name"],"light":b["name"],
           "dark_load":load(a),"light_load":load(b),"dark_t2":val(a,"t2"),"light_t2":val(b,"t2"),"pass":load_pair(a,b)}
      rec["span"]=abs(rec["dark_load"]-rec["light_load"]) if None not in (rec["dark_load"],rec["light_load"]) else -1
      endpoints.append(rec);save("FULL_ENDPOINTS.json",endpoints)
      if rec["pass"]:break
    if endpoints[-1]["pass"]:break
   if endpoints[-1]["pass"]:break
  if endpoints[-1]["pass"]:break
best=max([x for x in endpoints if x["span"]>=0],key=lambda x:x["span"],default=None)
# 3) Required I_PH sweep on the best real full-circuit configuration.
sweep=[];passed=False
if best:
  pc=best["photo"];base=power(best["mode"],best["diode_flip"])+control(best["vt3_flip"])+source()
  for i,u in enumerate((0,.1,.25,.5,1,2,3,4,6,8,12,16)):
    r=run(f"sweep_{i:02d}_{str(u).replace('.','p')}u",base+photo(pc["f2"],u,False),PWR+PH+["vt3_r6"],3.0,pc["vto"])
    sweep.append({"I_PH_uA":u,"run":r["name"],"LOAD_RMS_V":load(r),"SENS_mean_V":val(r,"sens"),"T1_mean_V":val(r,"t1"),
                  "T2_mean_V":val(r,"t2"),"DRV_mean_V":val(r,"drv"),"G1K1_RMS_V":val(r,"gk1","rms"),"G2K2_RMS_V":val(r,"gk2","rms")})
    save("IPH_SWEEP.json",sweep)
  good=[x for x in sweep if x["LOAD_RMS_V"] is not None]
  if good:
    lo=min(good,key=lambda x:x["LOAD_RMS_V"]);hi=max(good,key=lambda x:x["LOAD_RMS_V"]);span=hi["LOAD_RMS_V"]-lo["LOAD_RMS_V"]
    passed=lo["LOAD_RMS_V"]<=30 and hi["LOAD_RMS_V"]>=170 and span>=140
    result={"result":"PASS_REAL_LOAD_SWITCHING" if passed else "FAIL_REAL_LOAD_SWITCHING","off":lo,"on":hi,"span_Vrms":span,
            "criterion":{"off_max_Vrms":30,"on_min_Vrms":170,"span_min_Vrms":140},"config":best}
    save("RESULT.json",result)
    with (OUT/"IPH_SWEEP.csv").open("w",newline="",encoding="utf-8") as fh:
      w=csv.DictWriter(fh,fieldnames=list(sweep[0]));w.writeheader();w.writerows(sweep)
summary={"result":"PASS_REAL_LOAD_SWITCHING" if passed else "FAIL_REAL_LOAD_SWITCHING","best_endpoint":best,
         "photo_corners":photos,"tested_runs":len(ALL),"no_diagnostic_drive_in_sweep":True,
         "model_caveat":"KP501A corners constrained to published VGS(th)=1..3V and RDS(on)<=10ohm; not manufacturer SPICE."}
save("SUMMARY.json",summary);print(json.dumps(summary,ensure_ascii=False),flush=True)
if not passed:sys.exit(2)
