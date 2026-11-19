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
# Stage 4 targeted autonomous I_PH sweep using the already proven power/control configuration.
# No diagnostic source acts on DRV, T2 or SCR gates in these runs.
if os.environ.get("STAGE4_SWEEP_ONLY","0")=="1":
    sweep_values=(0,0.25,0.5,1,1.5,2,2.5,3,3.5,4,5,6,8,10,12,16)
    all_sets=[]
    accepted=[]
    for f1 in (False,True):
        for f2 in (False,True):
            net0=power("dc_tb",False)+control(False)+source()
            rows=[]
            for i,u in enumerate(sweep_values):
                rr=run(f"stage4_f{int(f1)}{int(f2)}_{i:02d}_{str(u).replace('.','p')}u",net0+photo(f1,f2,u),PWR+PH+["vt3_r6"],3.0)
                rows.append({"I_PH_uA":u,"run":rr["name"],"LOAD_RMS_V":load(rr),
                    "SENS_mean_V":rr.get("metrics",{}).get("sens",{}).get("mean"),
                    "T1_mean_V":rr.get("metrics",{}).get("t1",{}).get("mean"),
                    "T2_mean_V":rr.get("metrics",{}).get("t2",{}).get("mean"),
                    "DRV_mean_V":rr.get("metrics",{}).get("drv",{}).get("mean"),
                    "G1K1_RMS_V":rr.get("metrics",{}).get("gk1",{}).get("rms"),
                    "G2K2_RMS_V":rr.get("metrics",{}).get("gk2",{}).get("rms"),
                    "SW_RMS_V":rr.get("metrics",{}).get("sw",{}).get("rms")})
            good=[x for x in rows if x["LOAD_RMS_V"] is not None]
            if not good:
                rec={"f1":f1,"f2":f2,"rows":rows,"pass":False,"reason":"no numeric load"}
            else:
                lo=min(good,key=lambda x:x["LOAD_RMS_V"]);hi=max(good,key=lambda x:x["LOAD_RMS_V"])
                span=hi["LOAD_RMS_V"]-lo["LOAD_RMS_V"]
                ok=lo["LOAD_RMS_V"]<=30 and hi["LOAD_RMS_V"]>=170 and span>=140
                rec={"f1":f1,"f2":f2,"rows":rows,"min_load":lo,"max_load":hi,"span_V":span,"pass":ok}
                if ok:accepted.append(rec)
            all_sets.append(rec);save("STAGE4_ALL_SWEEPS.json",all_sets)
    result={"result":"PASS_REAL_LOAD_SWITCHING" if accepted else "FAIL_REAL_LOAD_SWITCHING",
        "criterion":{"off_max_Vrms":30,"on_min_Vrms":170,"span_min_Vrms":140},
        "fd320_model":{"dark_current_model_IS_A":2e-9,"dark_current_max_reference_A":50e-9,"junction_capacitance_F":80e-12,"reverse_BV_V":30},
        "accepted":accepted,"all_sets":all_sets}
    if accepted:
        best=max(accepted,key=lambda x:x["span_V"])
        result["selected"]=best
        for label,row in (("OFF",best["min_load"]),("ON",best["max_load"])):
            src=OUT/(row["run"]+".ms14");dst=OUT/f"7330744_STAGE4_{label}.ms14"
            if src.exists():dst.write_bytes(src.read_bytes())
        # Persist a flat CSV for the selected physical sweep.
        with (OUT/"STAGE4_IPH_SWEEP.csv").open("w",newline="",encoding="utf-8") as fh:
            cols=list(best["rows"][0]);cw=csv.DictWriter(fh,fieldnames=cols);cw.writeheader();cw.writerows(best["rows"])
    save("STAGE4_RESULT.json",result);print(json.dumps(result,ensure_ascii=False),flush=True)
    sys.exit(0 if accepted else 2)

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
