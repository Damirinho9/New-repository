"""Real NI Multisim COM block diagnostics. Source reference: docs/7330744/V6_SOURCE_REFERENCE.md.
Each block has its own native circuit, not the full circuit with a clamp source in parallel.
All runs execute in the same Windows job. Never promote diagnostic sources to the complete circuit.
"""
import csv,json,math,os,sys,subprocess,traceback,hashlib
from pathlib import Path
import numpy as np
from multisimforge import builder,check,xmlio
from multisimforge.parts import Library
from topology_models import patch_models,verify_saved_cards
OUT=Path("blocks-out");OUT.mkdir(exist_ok=True)
LIB=Library()
RESULTS={}
def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding="utf-8")
def x(ref,model,**pins):return "X"+ref+" "+model+" "+" ".join(f"{k}={v}" for k,v in pins.items())
def fet(ref,m,a,b,g,flip):return x(ref,m,D=a if flip else b,G=g,S=b if flip else a)
def bridge(mode):
    p={"dc_bt":{"V+":"0","V-":"br_top","AC1":"g18","AC2":"g25"},
       "dc_tb":{"V+":"br_top","V-":"0","AC1":"g18","AC2":"g25"},
       "ac_tb":{"AC1":"br_top","AC2":"0","V+":"g18","V-":"g25"},
       "ac_rev":{"AC1":"br_top","AC2":"0","V+":"g25","V-":"g18"}}[mode]
    return x("VD6","MDA2504",**p)
def power(mode,diode_flip=False):
    # RMON=1 ohm is an explicitly diagnostic current-sense resistor, not a source part.
    return [x("VS1","SCR",A="sw",K="n_int",G="g18"),"R8 g18 n_int 56",
      x("VD4","MUR1510G",A="g18" if diode_flip else "n_int",K="n_int" if diode_flip else "g18"),
      "RMON drv drvmon 1","XFU1 drvmon br_top 30_AMP",bridge(mode),
      x("VD5","MUR1510G",A="sw",K="g25"),"R9 g25 sw 56",x("VS2","SCR",A="n_int",K="sw",G="g25"),
      "C3 l n_int 47n CAPACITOR_VIRTUAL","XFU2 n_int n 30_AMP","RREF n_int 0 1G",
      "V1 ac_src n SIN(0 311.1269837 50)","RLINE ac_src l 10","RLOAD l sw 1k"]
def photo(flip1,flip2,iph):
    return ["R1 u_ctrl n_r1 4.7meg","R2 n_r1 sens 47k",
      x("VD1","PHOTO_DIODE_RATED",A="0",K="sens"),"C1 sens 0 470n CAP_ELECTROLIT_VIRTUAL","C2 u_ctrl 0 100n CAPACITOR_VIRTUAL",
      fet("VT1","2N6659","sens","t1","g12",flip1),"R3 g12 0 330","R4 u_ctrl t1 10k",
      fet("VT2","2N6659","t1","t2","g12",flip2),x("VD2","1N4742A",A="0",K="u_ctrl"),"R5 u_ctrl t2 5.1k",
      f"I1 sens 0 {iph*1e-6:.12g}"]
def control(flip):return [fet("VT3","IRFD110","t2","vt3_r6","0",flip),"R6 vt3_r6 drv 51","RU1 drv 0 10meg"]
def source():return [x("HL1","LED_red",A="led_a",K="u_ctrl"),x("VD3","MUR1510G",A="led_r",K="led_a"),"R7 led_r l 58k",x("XP1","HDR1X5",P1="sw",P2="l",P3="l",P4="n",P5="nc_xp1")]
PWR=["drv","drvmon","br_top","g18","g25","n_int","sw","l","ac_src","n"]
PH=["sens","t1","t2","u_ctrl","g12"]
def metrics(t,y,start,end):
    if start<t[0] or end>t[-1]+1e-10:raise ValueError("Incomplete measurement window")
    m=(t>start)&(t<end)
    tt=np.r_[start,t[m],end];yy=np.interp(tt,t,y)
    duration=end-start
    return {"mean":float(np.trapezoid(yy,tt)/duration),"rms":float(np.sqrt(np.trapezoid(yy*yy,tt)/duration)),
            "min":float(yy.min()),"max":float(yy.max())}
def run(name,net,nets,dur):
    record={"name":name,"diagnostic":not name.startswith("full_"),"duration_s":dur}
    RESULTS[name]=record
    file=OUT/(name+".ms14");(OUT/(name+".net")).write_text("\n".join(net)+"\n",encoding="utf-8")
    try:
        # Single diagnostic build: layout is not acceptance of the final drawing.
        spec={"netlist":"\n".join(net)+"\n","output":str(file),"net_names":True,"sheet":[21,11],"sim_time":str(int(dur*1000))+"ms","layout":{"GND":[[108,756],[540,756],[972,756],[1404,756],[1836,756]]}}
        builder.build(spec,lib=LIB,allow_fallback=True,auto_repair=True,repair_budget_s=12)
        root=xmlio.load(file)
        refs={s.split()[0][1:] for s in net if s.startswith("X")}
        refs &= {"VT1","VT2","VT3","VS1","VS2","VD3","VD4","VD5"}
        record["model_notes"]=patch_models(root,xmlio,refs)
        xmlio.save(root,file,compress=True);verify_saved_cards(xmlio.load(file),xmlio,refs)
        record["sha256"]=hashlib.sha256(file.read_bytes()).hexdigest()
        record["geometry"]=check.check_file(file)
        pinmap=check.inspect(file)["nets"]
        record["pinmap"]=pinmap
        # Fail on electrical topology inconsistency; geometry warnings saved, not assumed final PASS.
        critical=[z for z in record["geometry"].get("problems",[]) if "run on top of each other" not in z]
        if critical:raise RuntimeError("Structural problems: "+repr(critical))
        dest=OUT/(name+"_csv")
        p=subprocess.run([sys.executable,"-m","multisimforge","sim",str(file.resolve()),"--nets",",".join(nets),"--tran",f"{dur},8000","--csv",str(dest.resolve())],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=150)
        (OUT/(name+"_sim.log")).write_text(p.stdout+"\n"+p.stderr,encoding="utf-8")
        j=json.loads(p.stdout);record["sim_status"]=j.get("status");record["sim_warnings"]=j.get("warnings")
        if p.returncode or j.get("status") not in ("PASS","WARN") or j.get("failures") or j.get("missing"):raise RuntimeError("Native sim failed")
        rows=list(csv.DictReader((dest/"tran.csv").open(encoding="utf-8-sig")))
        t=np.array([float(r["time"]) for r in rows]);data={n:np.array([float(r[n]) for r in rows]) for n in nets}
        if len(t)<100 or not np.isfinite(t).all() or np.any(np.diff(t)<0) or t[-1]<dur*.95:raise RuntimeError("Incomplete native transient")
        if not all(np.isfinite(v).all() for v in data.values()):raise RuntimeError("Nonfinite native transient")
        end=t[-1];start=end-.08
        if "l" in data and "sw" in data:
            data["load"]=data["l"]-data["sw"];data["load_i"]=data["load"]/1000
            data["gk1"]=data["g18"]-data["n_int"];data["gk2"]=data["g25"]-data["sw"]
            data["drive_i"]=data["drv"]-data["drvmon"]
            # Report polarity coverage from each supply half-wave separately, only on the settled window.
            line=data["ac_src"]-data["n"]
            m=t>=start
            record["positive_peak_load_V"]=float(np.max(np.abs(data["load"][m&(line>150)])))
            record["negative_peak_load_V"]=float(np.max(np.abs(data["load"][m&(line<-150)])))
        record["metrics"]={k:metrics(t,v,start,end) for k,v in data.items()}
        record["window_s"]=[float(start),float(end)]
        record["status"]="MEASURED"
    except Exception as e:
        record["status"]="FAIL";record["error"]=repr(e)
        (OUT/(name+"_error.txt")).write_text(traceback.format_exc(),encoding="utf-8")
    save("all_measurements.json",RESULTS)
    print(name,record["status"],record.get("metrics",{}).get("load",{}).get("rms"),flush=True)
    return record

def load(a):return a.get("metrics",{}).get("load",{}).get("rms")
def pair(a,b):
    if load(a) is None or load(b) is None:return False
    lo,hi=sorted([a,b],key=load)
    return load(lo)<=30 and load(hi)>=170 and load(hi)-load(lo)>=140 and min(hi.get("positive_peak_load_V",0),hi.get("negative_peak_load_V",0))>=170
def ordered_power(off,on):
    return pair(off,on) and load(off)<=30 and load(on)>=170

def amps(a):return a.get("metrics",{}).get("drive_i",{}).get("rms")
# Stage 4 continuation after run 44529980598.
# f00 was measured from 0..500 uA with LOAD_RMS ~= 0.109 V throughout and is rejected.
# Known proven downstream configuration from native block test: bridge dc_tb, VD4 default polarity,
# VT3 orientation flip=False. No diagnostic source is present in these full-circuit sweeps.
coarse=(0,1,2,4,8,16,25,40,60,80,100,150,200,250,300,400,500,750,1000)
rows=[];fine=[];results=[]
base_net=power("dc_tb",False)+control(False)+source()
for f1,f2 in ((False,True),(True,False),(True,True)):
    pts=[]
    for i,u in enumerate(coarse):
        r=run(f"cont_f{int(f1)}{int(f2)}_{i:02d}_{str(u).replace('.','p')}u",base_net+photo(f1,f2,u),PWR+PH+["vt3_r6"],3.0)
        row={"f1":f1,"f2":f2,"I_PH_uA":u,"run":r["name"],"LOAD_RMS_V":load(r),
             "SENS_mean_V":r.get("metrics",{}).get("sens",{}).get("mean"),
             "T1_mean_V":r.get("metrics",{}).get("t1",{}).get("mean"),
             "T2_mean_V":r.get("metrics",{}).get("t2",{}).get("mean"),
             "DRV_mean_V":r.get("metrics",{}).get("drv",{}).get("mean"),
             "G1K1_RMS_V":r.get("metrics",{}).get("gk1",{}).get("rms"),
             "G2K2_RMS_V":r.get("metrics",{}).get("gk2",{}).get("rms"),
             "SW_RMS_V":r.get("metrics",{}).get("sw",{}).get("rms")}
        rows.append(row);pts.append(row);save("IPH_SWEEP_CONTINUATION.json",rows)
        good=[p for p in pts if p["LOAD_RMS_V"] is not None]
        if len(good)>=2:
            mn=min(good,key=lambda p:p["LOAD_RMS_V"]);mx=max(good,key=lambda p:p["LOAD_RMS_V"])
            if mn["LOAD_RMS_V"]<=30 and mx["LOAD_RMS_V"]>=170 and mx["LOAD_RMS_V"]-mn["LOAD_RMS_V"]>=140:
                break
    good=[p for p in pts if p["LOAD_RMS_V"] is not None]
    if not good:
        results.append({"f1":f1,"f2":f2,"pass":False,"error":"no numeric points"});continue
    mn=min(good,key=lambda p:p["LOAD_RMS_V"]);mx=max(good,key=lambda p:p["LOAD_RMS_V"])
    # Locate the largest adjacent jump for a fine sweep only when a real coarse transition exists.
    edge=None;jump=0
    for p0,p1 in zip(good,good[1:]):
        d=abs(p1["LOAD_RMS_V"]-p0["LOAD_RMS_V"])
        if d>jump:jump=d;edge=(p0,p1)
    if edge and jump>=40:
        lo,hi=sorted([edge[0]["I_PH_uA"],edge[1]["I_PH_uA"]])
        for k in range(1,20):
            u=lo+(hi-lo)*k/20
            r=run(f"contfine_f{int(f1)}{int(f2)}_{k:02d}_{u:.6g}u".replace(".","p"),base_net+photo(f1,f2,u),PWR+PH+["vt3_r6"],3.0)
            q={"f1":f1,"f2":f2,"I_PH_uA":u,"run":r["name"],"LOAD_RMS_V":load(r),
               "SENS_mean_V":r.get("metrics",{}).get("sens",{}).get("mean"),
               "T1_mean_V":r.get("metrics",{}).get("t1",{}).get("mean"),
               "T2_mean_V":r.get("metrics",{}).get("t2",{}).get("mean"),
               "DRV_mean_V":r.get("metrics",{}).get("drv",{}).get("mean"),
               "G1K1_RMS_V":r.get("metrics",{}).get("gk1",{}).get("rms"),
               "G2K2_RMS_V":r.get("metrics",{}).get("gk2",{}).get("rms"),
               "SW_RMS_V":r.get("metrics",{}).get("sw",{}).get("rms")}
            fine.append(q);save("IPH_FINE_CONTINUATION.json",fine)
        allp=good+[q for q in fine if q["f1"]==f1 and q["f2"]==f2 and q["LOAD_RMS_V"] is not None]
        mn=min(allp,key=lambda p:p["LOAD_RMS_V"]);mx=max(allp,key=lambda p:p["LOAD_RMS_V"])
    span=mx["LOAD_RMS_V"]-mn["LOAD_RMS_V"]
    results.append({"f1":f1,"f2":f2,"min_load":mn,"max_load":mx,"span_V":span,
      "pass":mn["LOAD_RMS_V"]<=30 and mx["LOAD_RMS_V"]>=170 and span>=140})
    save("IPH_CONFIG_RESULTS_CONTINUATION.json",results)
    if results[-1]["pass"]:break
winner=next((q for q in results if q["pass"]),None)
summary={"result":"PASS_REAL_LOAD_SWITCHING" if winner else "FAIL_REAL_LOAD_SWITCHING",
 "winner":winner,"results":results,
 "prior_f00":{"range_uA":[0,500],"load_range_Vrms":[0.10908006406418638,0.10975769438444444],"status":"REJECTED"},
 "criterion":{"off_max_Vrms":30,"on_min_Vrms":170,"span_min_Vrms":140},
 "configuration":{"bridge":"dc_tb","VD4_flip":False,"VT3_flip":False},
 "note":"Only physical K->A photocurrent direction used. No force-T2/DRV/gate source in sweep."}
save("STAGE4_RESULT.json",summary)
if rows:
    with (OUT/"IPH_SWEEP_CONTINUATION.csv").open("w",newline="",encoding="utf-8") as fh:
        cols=list(rows[0]);ww=csv.DictWriter(fh,fieldnames=cols);ww.writeheader();ww.writerows(rows)
if fine:
    with (OUT/"IPH_FINE_CONTINUATION.csv").open("w",newline="",encoding="utf-8") as fh:
        cols=list(fine[0]);ww=csv.DictWriter(fh,fieldnames=cols);ww.writeheader();ww.writerows(fine)
print(json.dumps(summary,ensure_ascii=False),flush=True)
if not winner:sys.exit(2)
