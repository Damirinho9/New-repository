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
def run(name,net,nets,dur,scope=False,points=8000,final_layout=False):
    net=list(net)
    if scope:
        # Harvested native SCOPE order is 1,2,4,3,5,6. This yields A=SENS-0 and B=L-SW.
        net += ["XSC1 sens 0 sw l 0 0 SCOPE"]
    record={"name":name,"diagnostic":not name.startswith("full_"),"duration_s":dur,"scope":scope}
    RESULTS[name]=record
    file=OUT/(name+".ms14");(OUT/(name+".net")).write_text("\n".join(net)+"\n",encoding="utf-8")
    try:
        # Final files use an explicit source-like layout. Diagnostics may use compact auto-layout.
        layout={"GND":[[72,144],[252,558],[432,558],[666,558],[900,558],[1080,558],[1233,558],[1404,648],[1512,648],[270,558],[900,810]]}
        if final_layout:
            layout.update({
              "R1":[144,180,90],"R2":[144,270,90],"XVD1":[144,378,90],"C1":[252,378,90],"C2":[306,180,90],
              "XVT1":[432,288],"R3":[432,414,90],"R4":[504,180,90],"XVT2":[576,288],"XVD2":[666,180,90],
              "R5":[720,234,90],"XVT3":[756,378],"R6":[846,342],"XHL1":[828,144,90],"XVD3":[900,198,90],
              "RU1":[900,432,90],"R7":[990,234],"XVS1":[1080,414,90],"R8":[1152,486,90],"XVD4":[1233,486,90],
              "XFU1":[1008,324],"XVD6":[1197,342],"XVD5":[1323,198],"R9":[1323,270],"XVS2":[1404,342,90],
              "C3":[1512,450,90],"XFU2":[1512,576],"XXP1":[1908,306,90],
              "I1":[270,486,90],"I2":[360,486,90],"V1":[1908,648,90],"RLINE":[1800,648],"RLOAD":[1800,144,90],"RREF":[1656,756,90]
            })
            if scope:
                layout["XSC1"]=[1566,756]
        spec={"netlist":"\n".join(net)+"\n","output":str(file),"net_names":True,"sheet":[22,12],"sim_time":f"{dur:.6g}s","layout":layout,
              "colors":{"sens":"red","sw":"blue","g18":"green","g25":"green"}}
        if scope:
            spec["instruments"]={"XSC1":{"timebase":"100ms","a_scale":"5V","b_scale":"100V","a_coupling":"dc","b_coupling":"dc","trigger":"none"}}
        builder.build(spec,lib=LIB,allow_fallback=False if final_layout else True,auto_repair=True,repair_budget_s=90 if final_layout else 12)
        root=xmlio.load(file)
        refs={s.split()[0][1:] for s in net if s.startswith("X")}
        refs &= {"VT1","VT2","VT3","VS1","VS2","VD1","VD3","VD4","VD5"}
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
        p=subprocess.run([sys.executable,"-m","multisimforge","sim",str(file.resolve()),"--nets",",".join(nets),"--tran",f"{dur},{points}","--csv",str(dest.resolve())],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=150)
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
            if "drvmon" in data:
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
# Stage 4 targeted autonomous I_PH sweep using the already proven power/control configuration.
# No diagnostic source acts on DRV, T2 or SCR gates in these runs.
if os.environ.get("PHASEA_FINAL_ONLY","0")=="1":
    FINAL=Path("phaseA-final"); FINAL.mkdir(exist_ok=True)
    os.environ["SCR_VTH"]="0.32"
    os.environ["KP707_VTO"]="1.5"
    f1,f2=False,True

    def power_final():
        return [
          x("VS1","SCR",A="sw",K="n_int",G="g18"),"R8 g18 n_int 56",
          x("VD4","MUR1510G",A="n_int",K="g18"),"XFU1 drv br_top 30_AMP",bridge("dc_tb"),
          x("VD5","MUR1510G",A="sw",K="g25"),"R9 g25 sw 56",x("VS2","SCR",A="n_int",K="sw",G="g25"),
          "C3 l n_int 47n CAPACITOR_VIRTUAL","XFU2 n_int n 30_AMP","RREF n_int 0 1G",
          "V1 ac_src n SIN(0 311.1269837 50)","RLINE ac_src l 10","RLOAD l sw 1k"
        ]

    FINAL_NETS=["drv","br_top","g18","g25","n_int","sw","l","ac_src","n"]+PH+["vt3_r6"]
    base=power_final()+control(False)+source()

    fine_values=[7000,7050,7100,7150,7200,7250,7300,7350,7400,7450,7500]
    fine=[]
    for u in fine_values:
        rr=run(f"phaseA_fine_{u}u",base+photo(f1,f2,u),FINAL_NETS,1.0,points=6000,final_layout=True)
        fine.append({"I_PH_uA":u,"run":rr["name"],"LOAD_RMS_V":load(rr),
          "SENS_mean_V":rr.get("metrics",{}).get("sens",{}).get("mean"),
          "T1_mean_V":rr.get("metrics",{}).get("t1",{}).get("mean"),
          "T2_mean_V":rr.get("metrics",{}).get("t2",{}).get("mean"),
          "DRV_mean_V":rr.get("metrics",{}).get("drv",{}).get("mean")})
        save("PHASE_A_FINE_SWEEP.json",fine)

    dark_num=run("phaseA_dark_numeric",base+photo(f1,f2,0),FINAL_NETS,1.0,points=6000,final_layout=True)
    light_num=run("phaseA_light_numeric",base+photo(f1,f2,8000),FINAL_NETS,1.0,points=6000,final_layout=True)
    mids=[z for z in fine if z["LOAD_RMS_V"] is not None and 30 < z["LOAD_RMS_V"] < 170]
    if not mids:
        raise SystemExit("PHASE_A_FINAL: no converged threshold state between 30 and 170 Vrms")
    threshold=min(mids,key=lambda z:abs(z["LOAD_RMS_V"]-110))
    if load(dark_num) is None or load(dark_num)>30:
        raise SystemExit("PHASE_A_FINAL: DARK not OFF")
    if load(light_num) is None or load(light_num)<170:
        raise SystemExit("PHASE_A_FINAL: LIGHT not ON")

    selected={"DARK":0.0,"THRESHOLD":float(threshold["I_PH_uA"]),"LIGHT":8000.0}
    final_records={}
    for label,u in selected.items():
        rr=run(f"phaseA_final_{label.lower()}",base+photo(f1,f2,u),FINAL_NETS,1.0,scope=True,points=6000,final_layout=True)
        if load(rr) is None:
            raise SystemExit("PHASE_A_FINAL: "+label+" no numeric result with XSC1")
        dest=FINAL/f"7330744_PhotoRelay_V6_{label}.ms14"
        dest.write_bytes((OUT/(rr["name"]+".ms14")).read_bytes())
        final_records[label]={"I_PH_uA":u,"LOAD_RMS_V":load(rr),
          "SENS_mean_V":rr["metrics"]["sens"]["mean"],"T1_mean_V":rr["metrics"]["t1"]["mean"],
          "T2_mean_V":rr["metrics"]["t2"]["mean"],"DRV_mean_V":rr["metrics"]["drv"]["mean"],
          "sha256":hashlib.sha256(dest.read_bytes()).hexdigest(),"size":dest.stat().st_size,
          "check":rr.get("geometry"),"pinmap":rr.get("pinmap")}
    if final_records["DARK"]["LOAD_RMS_V"]>30 or final_records["LIGHT"]["LOAD_RMS_V"]<170:
        raise SystemExit("PHASE_A_FINAL: XSC1 changed DARK/LIGHT acceptance")
    if not (30 < final_records["THRESHOLD"]["LOAD_RMS_V"] < 170):
        raise SystemExit("PHASE_A_FINAL: XSC1 threshold state not intermediate")

    uth=selected["THRESHOLD"]*1e-6
    ulight=selected["LIGHT"]*1e-6
    sensor=photo(f1,f2,0)[:-1]
    sensor += [
      f"I1 sens 0 PULSE(0 {uth:.12g} 200m 20m 20m 750m 2s)",
      f"I2 sens 0 PULSE(0 {ulight-uth:.12g} 500m 20m 20m 300m 2s)"
    ]
    tr=run("phaseA_final_transient",base+sensor,FINAL_NETS,1.2,scope=True,points=12000,final_layout=True)
    if tr.get("status")!="MEASURED":
        raise SystemExit("PHASE_A_FINAL: transient did not converge")
    tpath=OUT/"phaseA_final_transient_csv"/"tran.csv"
    rows=list(csv.DictReader(tpath.open(encoding="utf-8-sig")))
    tt=np.array([float(z["time"]) for z in rows])
    lv=np.array([float(z["l"])-float(z["sw"]) for z in rows])
    def wrms(a,b):
        mm=(tt>=a)&(tt<=b)
        if mm.sum()<20: return None
        return float(np.sqrt(np.mean(lv[mm]*lv[mm])))
    seq={"dark1_Vrms":wrms(.08,.18),"threshold1_Vrms":wrms(.30,.45),"light_Vrms":wrms(.60,.75),
         "threshold2_Vrms":wrms(.84,.93),"dark2_Vrms":wrms(1.04,1.15)}
    if seq["dark1_Vrms"] is None or seq["dark2_Vrms"] is None or max(seq["dark1_Vrms"],seq["dark2_Vrms"])>30:
        raise SystemExit("PHASE_A_FINAL: transient dark windows failed")
    if seq["light_Vrms"] is None or seq["light_Vrms"]<170:
        raise SystemExit("PHASE_A_FINAL: transient light window failed")
    if seq["threshold1_Vrms"] is None or not (30<seq["threshold1_Vrms"]<170):
        raise SystemExit("PHASE_A_FINAL: transient threshold window failed")
    tdest=FINAL/"7330744_PhotoRelay_V6_TRANSIENT.ms14"
    tdest.write_bytes((OUT/"phaseA_final_transient.ms14").read_bytes())
    (FINAL/"TRANSIENT.csv").write_bytes(tpath.read_bytes())
    (FINAL/"FINE_SWEEP.csv").write_text(
      "I_PH_uA,LOAD_RMS_V,SENS_mean_V,T1_mean_V,T2_mean_V,DRV_mean_V\n"+
      "\n".join(f'{z["I_PH_uA"]},{z["LOAD_RMS_V"]},{z["SENS_mean_V"]},{z["T1_mean_V"]},{z["T2_mean_V"]},{z["DRV_mean_V"]}' for z in fine),
      encoding="utf-8"
    )
    summary={"result":"PASS_NUMERIC_PHASE_A_FINAL",
      "model_scope":"Educational functional model only, not T123-250 hardware validation.",
      "SCR_VTH_V":0.32,"bridge_mode":"dc_tb","selected":selected,"states":final_records,"transient":seq,
      "transient_sha256":hashlib.sha256(tdest.read_bytes()).hexdigest(),"transient_size":tdest.stat().st_size,
      "limitations":["I_PH is a simulation control current; LIGHT=8mA is not a calibrated FD320 lux conversion.",
                     "C1/C2/C3 are simulation assumptions because the source BOM omits capacitances.",
                     "VS1/VS2 use a functional cathode-referenced SCR surrogate at 0.32V, not an exact T123-250 hardware model.",
                     "RREF=1G is simulation-only to reference separated CASE and N_INT."]}
    (FINAL/"PHASE_A_SUMMARY.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False),flush=True)
    sys.exit(0)

if os.environ.get("STAGE4_SWEEP_ONLY","0")=="1":
    # Hardware note: exact T123-250 is incompatible with the 1k educational load
    # (I_H up to 0.30A > 220V/1k) and requires gate drive far above this source circuit.
    # Therefore only this Stage-4 teaching model uses an explicitly functional SCR surrogate.
    f1,f2=False,True   # best source-ambiguous KP501 D/S mapping from prior native endpoints
    net0=power("dc_tb",False)+control(False)+source()
    candidates=[]
    for sv in (0.30,0.32,0.34,0.36,0.38,0.40):
        os.environ["SCR_VTH"]=str(sv)
        dark=run(f"scr{str(sv).replace('.','p')}_dark",net0+photo(f1,f2,0),PWR+PH+["vt3_r6"],1.5)
        light=run(f"scr{str(sv).replace('.','p')}_8mA",net0+photo(f1,f2,8000),PWR+PH+["vt3_r6"],1.5)
        ld,ll=load(dark),load(light)
        span=abs(ll-ld) if ld is not None and ll is not None else None
        rec={"SCR_VTH_V":sv,"dark":dark["name"],"light":light["name"],"dark_load_V":ld,"light_load_V":ll,"span_V":span,
             "dark_g1k1_peak_V":dark.get("metrics",{}).get("gk1",{}).get("max"),
             "dark_g2k2_peak_V":dark.get("metrics",{}).get("gk2",{}).get("max"),
             "light_g1k1_peak_V":light.get("metrics",{}).get("gk1",{}).get("max"),
             "light_g2k2_peak_V":light.get("metrics",{}).get("gk2",{}).get("max"),
             "light_t2_V":light.get("metrics",{}).get("t2",{}).get("mean"),
             "pass":ld is not None and ll is not None and ld<=30 and ll>=170 and ll-ld>=140}
        candidates.append(rec);save("STAGE4_FUNCTIONAL_SCR_QUALIFICATION.json",candidates)
    viable=[x for x in candidates if x["pass"]]
    if not viable:
        measured=[x for x in candidates if x["span_V"] is not None]
        best=max(measured,key=lambda x:x["span_V"]) if measured else None
        result={"result":"FAIL_REAL_LOAD_SWITCHING","phase":"functional_scr_qualification","best":best,"candidates":candidates,
          "criterion":{"off_max_Vrms":30,"on_min_Vrms":170,"span_min_Vrms":140},
          "hardware_limit":"T123-250 exact hardware characteristics are not represented by the 1k educational surrogate."}
        save("STAGE4_RESULT.json",result);print(json.dumps(result,ensure_ascii=False),flush=True);sys.exit(2)
    best=max(viable,key=lambda x:x["span_V"])
    os.environ["SCR_VTH"]=str(best["SCR_VTH_V"])
    sweep_values=(0,250,500,750,1000,1500,2000,2500,3000,3500,4000,4500,5000,5500,6000,6500,7000,7500,8000)
    rows=[]
    for i,u in enumerate(sweep_values):
        rr=run(f"stage4_func_{i:02d}_{u}u",net0+photo(f1,f2,u),PWR+PH+["vt3_r6"],1.5)
        rows.append({"I_PH_uA":u,"run":rr["name"],"LOAD_RMS_V":load(rr),
          "SENS_mean_V":rr.get("metrics",{}).get("sens",{}).get("mean"),
          "T1_mean_V":rr.get("metrics",{}).get("t1",{}).get("mean"),
          "T2_mean_V":rr.get("metrics",{}).get("t2",{}).get("mean"),
          "DRV_mean_V":rr.get("metrics",{}).get("drv",{}).get("mean"),
          "DRV_CURRENT_RMS_A":rr.get("metrics",{}).get("drive_i",{}).get("rms"),
          "G1K1_RMS_V":rr.get("metrics",{}).get("gk1",{}).get("rms"),
          "G2K2_RMS_V":rr.get("metrics",{}).get("gk2",{}).get("rms")})
        save("STAGE4_IPH_SWEEP.json",rows)
    good=[x for x in rows if x["LOAD_RMS_V"] is not None]
    lo=min(good,key=lambda x:x["LOAD_RMS_V"]);hi=max(good,key=lambda x:x["LOAD_RMS_V"]);span=hi["LOAD_RMS_V"]-lo["LOAD_RMS_V"]
    passed=lo["LOAD_RMS_V"]<=30 and hi["LOAD_RMS_V"]>=170 and span>=140
    result={"result":"PASS_REAL_LOAD_SWITCHING" if passed else "FAIL_REAL_LOAD_SWITCHING","phase":"functional_scr_I_PH_sweep",
      "selected_SCR_VTH_V":best["SCR_VTH_V"],"min_load":lo,"max_load":hi,"span_V":span,"rows":rows,
      "criterion":{"off_max_Vrms":30,"on_min_Vrms":170,"span_min_Vrms":140},
      "model_scope":"Educational 1k-load functional SCR surrogate only; not T123-250 hardware validation."}
    with (OUT/"STAGE4_IPH_SWEEP.csv").open("w",newline="",encoding="utf-8") as fh:
        cols=list(rows[0]);cw=csv.DictWriter(fh,fieldnames=cols);cw.writeheader();cw.writerows(rows)
    if passed:
        for label,row in (("OFF",lo),("ON",hi)):
            src=OUT/(row["run"]+".ms14");dst=OUT/f"7330744_STAGE4_{label}.ms14"
            if src.exists():dst.write_bytes(src.read_bytes())
    save("STAGE4_RESULT.json",result);print(json.dumps(result,ensure_ascii=False),flush=True);sys.exit(0 if passed else 2)

# Power: inject a real controlled path or bounded current into DRV, never into either SCR gate directly.
# Both source-ambiguous bridge assignments and diode polarity are tested.
power_pairs=[]
for mode in ("dc_bt","dc_tb","ac_tb","ac_rev"):
    for dp in (False,True):
        tag=f"p_{mode}_d{int(dp)}"
        n=power(mode,dp)
        off=run(tag+"_open",n+["RDRV drv 0 1G"],PWR,.24)
        on=run(tag+"_closed",n+["RDRV drv 0 10"],PWR,.24)
        power_pairs.append({"mode":mode,"diode_flip":dp,"off":off["name"],"on":on["name"],"pass":ordered_power(off,on),"injection":"10 ohm DRV-CASE closure vs 1G"})
        if not ordered_power(off,on):
            for sign in (-1,1):
                forced=run(tag+("_sink" if sign>0 else "_source"),n+[("IDRV drv 0 0.08" if sign>0 else "IDRV 0 drv 0.08")],PWR,.24)
                power_pairs.append({"mode":mode,"diode_flip":dp,"off":off["name"],"on":forced["name"],"pass":ordered_power(off,forced),"injection":"bounded 80mA diagnostic current"})
        save("power_pairs.json",power_pairs)
passed=[r for r in power_pairs if r["pass"]]
# If no power proof exists still obtain photo and control measurements, but never claim stage PASS.
candidates=passed[:3] or [{"mode":"dc_bt","diode_flip":False}]
control_pairs=[]
for k,c in enumerate(candidates):
    for flip in (False,True):
        n=power(c["mode"],c["diode_flip"])+control(flip)
        # No force-DRV source in this block; only T2 port is excited.
        a=run(f"c{k}_f{int(flip)}_pos",n+["VT2TEST t2 0 6"],PWR+["t2","vt3_r6"],.24)
        b=run(f"c{k}_f{int(flip)}_neg",n+["VT2TEST t2 0 -6"],PWR+["t2","vt3_r6"],.24)
        control_pairs.append({"mode":c["mode"],"diode_flip":c["diode_flip"],"flip":flip,"a":a["name"],"b":b["name"],"pass":pair(a,b)})
        save("control_pairs.json",control_pairs)
# Photo block first uses an explicit isolated bench DC rail, swept within a stated assumption.
# Importantly its output is measured at T2, not judged using external gate actuation.
photo_pairs=[]
for f1 in (False,True):
    for f2 in (False,True):
        a=run(f"s_f{int(f1)}{int(f2)}_dark",photo(f1,f2,0)+["VTEST u_ctrl 0 12"],PH,3.0)
        b=run(f"s_f{int(f1)}{int(f2)}_light",photo(f1,f2,8)+["VTEST u_ctrl 0 12"],PH,3.0)
        ma=a.get("metrics",{}).get("t2",{}).get("mean");mb=b.get("metrics",{}).get("t2",{}).get("mean")
        photo_pairs.append({"f1":f1,"f2":f2,"a":a["name"],"b":b["name"],"t2_dark_V":ma,"t2_light_V":mb,"t2_span_V":abs(ma-mb) if ma is not None and mb is not None else None})
        save("photo_pairs.json",photo_pairs)
# Autonomous full circuit. No VT2TEST, IDRV, VTEST, RDRV or current source forcing the power stage.
# Only I1 represents photogenerated current. RMON and RREF are explicitly testbench elements.
full_pairs=[]
for k,c in enumerate([r for r in control_pairs if r["pass"]][:2] or control_pairs[:2]):
    for q in photo_pairs:
        f1,f2=q["f1"],q["f2"]
        n=power(c["mode"],c["diode_flip"])+control(c["flip"])+source()
        a=run(f"full_{k}_{int(f1)}{int(f2)}_dark",n+photo(f1,f2,0),PWR+PH+["vt3_r6"],3.0)
        b=run(f"full_{k}_{int(f1)}{int(f2)}_light",n+photo(f1,f2,8),PWR+PH+["vt3_r6"],3.0)
        # Require a corresponding measured change at the bridge input as well as load, not merely a changed sensor.
        drive_change=abs(amps(a)-amps(b)) if amps(a) is not None and amps(b) is not None else None
        def count_refs(r):
            return {m.split(".",1)[0] for pins in r.get("pinmap",{}).values() for m in pins}
        required=set("R1 R2 VD1 C1 C2 VT1 R3 R4 VT2 VD2 R5 VT3 R6 HL1 VD3 RU1 R7 VS1 R8 VD4 FU1 VD6 VD5 R9 VS2 C3 FU2 XP1".split())
        complete=required<=count_refs(a) and required<=count_refs(b) and not ({"IDRV","RDRV","VT2TEST","VTEST"}&(count_refs(a)|count_refs(b)))
        rec={"config":c,"photo":q,"dark":a["name"],"light":b["name"],"source_complete":complete,"drive_change_A":drive_change,"pass":pair(a,b) and complete and drive_change is not None and drive_change>1e-5}
        full_pairs.append(rec);save("full_pairs.json",full_pairs)
        if rec["pass"]:break
    if full_pairs and full_pairs[-1]["pass"]:break
# Pick the autonomous configuration with the largest measured endpoint load change.
# The I_PH sweep is always attempted when at least one complete autonomous pair produced numeric data,
# even if the initial 0/8 uA endpoints did not satisfy the acceptance thresholds.
def endpoint_span(rec):
    a=RESULTS.get(rec["dark"],{});b=RESULTS.get(rec["light"],{})
    return abs(load(a)-load(b)) if load(a) is not None and load(b) is not None else -1
numeric_full=[r for r in full_pairs if r.get("source_complete") and endpoint_span(r)>=0]
best_full=max(numeric_full,key=endpoint_span) if numeric_full else None
sweep=[]
sweep_pass=False
if best_full:
    c=best_full["config"];q=best_full["photo"];f1,f2=q["f1"],q["f2"]
    base_net=power(c["mode"],c["diode_flip"])+control(c["flip"])+source()
    for i,u in enumerate((0,0.25,0.5,1,2,4,8,12,16,25)):
        r=run(f"iph_{i:02d}_{str(u).replace('.','p')}u",base_net+photo(f1,f2,u),PWR+PH+["vt3_r6"],3.0)
        sweep.append({"I_PH_uA":u,"run":r["name"],"LOAD_RMS_V":load(r),
          "SENS_mean_V":r.get("metrics",{}).get("sens",{}).get("mean"),
          "T1_mean_V":r.get("metrics",{}).get("t1",{}).get("mean"),
          "T2_mean_V":r.get("metrics",{}).get("t2",{}).get("mean"),
          "DRV_mean_V":r.get("metrics",{}).get("drv",{}).get("mean"),
          "G1K1_RMS_V":r.get("metrics",{}).get("gk1",{}).get("rms"),
          "G2K2_RMS_V":r.get("metrics",{}).get("gk2",{}).get("rms"),
          "SW_RMS_V":r.get("metrics",{}).get("sw",{}).get("rms")})
        save("IPH_SWEEP.json",sweep)
    good=[x for x in sweep if x["LOAD_RMS_V"] is not None]
    if good:
        lo=min(good,key=lambda x:x["LOAD_RMS_V"]);hi=max(good,key=lambda x:x["LOAD_RMS_V"])
        sweep_pass=lo["LOAD_RMS_V"]<=30 and hi["LOAD_RMS_V"]>=170 and hi["LOAD_RMS_V"]-lo["LOAD_RMS_V"]>=140
        sweep_result={"result":"PASS_REAL_LOAD_SWITCHING" if sweep_pass else "FAIL_REAL_LOAD_SWITCHING",
          "min_load":lo,"max_load":hi,"span_V":hi["LOAD_RMS_V"]-lo["LOAD_RMS_V"],
          "criterion":{"off_max_Vrms":30,"on_min_Vrms":170,"span_min_Vrms":140},
          "selected_config":best_full}
        save("IPH_SWEEP_RESULT.json",sweep_result)
        with (OUT/"IPH_SWEEP.csv").open("w",newline="",encoding="utf-8") as fh:
            cols=list(sweep[0]);w=csv.DictWriter(fh,fieldnames=cols);w.writeheader();w.writerows(sweep)
# Require both diagnostic proofs and autonomous verification on exactly the same candidate for the block-level PASS.
win=next((r for r in full_pairs if r["pass"] and r["config"]["pass"] and any(p["pass"] and p["mode"]==r["config"]["mode"] and p["diode_flip"]==r["config"]["diode_flip"] for p in power_pairs)),None)
summary={"result":"PASS_NATIVE_BLOCK_DIAGNOSTICS" if win else "FAIL_OR_INCOMPLETE_BLOCK_DIAGNOSTICS",
"real_load_switching":"PASS_REAL_LOAD_SWITCHING" if sweep_pass else "FAIL_REAL_LOAD_SWITCHING",
"power_pass_count":len(passed),"control_pass_count":sum(r["pass"] for r in control_pairs),"autonomous_pass_count":sum(r["pass"] for r in full_pairs),"tested":len(RESULTS),"selected":win,"sweep_config":best_full,
"limitations":"Native COM transient only; diagnostic plots and geometry must be verified separately; model proxies not certified hardware."}
save("SUMMARY.json",summary);print(json.dumps(summary),flush=True)
if not sweep_pass:sys.exit(2)
