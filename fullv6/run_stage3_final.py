import csv, json, math, shutil, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
SCAN=ROOT/"stage3-out"
OUT=ROOT/"stage3-final"
OUT.mkdir(parents=True,exist_ok=True)
sel=json.loads((OUT/"stage3_selected_currents.json").read_text(encoding="utf-8"))
states=sel["states_uA"]
build_script=ROOT/"fullv6"/"build_stage3_sim.py"
nets=["sens","u_ctrl","t1","t2","drv","g1","g2","l","sw"]

def call(args,log,require=True):
    p=subprocess.run(args,capture_output=True,text=True,encoding="utf-8",errors="replace")
    Path(log).write_text((p.stdout or "")+"\n--- STDERR ---\n"+(p.stderr or ""),encoding="utf-8")
    if require and p.returncode!=0:
        raise RuntimeError(f"command failed rc={p.returncode}: {args}; see {log}")
    return p

def tail_metrics(path,start=0.8):
    data=[]
    with open(path,newline="",encoding="utf-8") as f:
        rd=csv.DictReader(f)
        for r in rd:
            if float(r["time"])>=start:
                data.append({k:float(v) for k,v in r.items()})
    if not data: raise RuntimeError(f"no tail data in {path}")
    def st(vals):
        n=len(vals); mean=sum(vals)/n
        return {"mean_V":mean,"rms_V":math.sqrt(sum(v*v for v in vals)/n),"min_V":min(vals),"max_V":max(vals),"pp_V":max(vals)-min(vals)}
    m={n:st([r[n] for r in data]) for n in nets}
    m["load"]=st([r["l"]-r["sw"] for r in data])
    m["samples_tail"]=len(data)
    return m

summary=[]
labels={"dark":"темнота","threshold":"область порога","light":"свет"}
for state in ("dark","threshold","light"):
    u=float(states[state]); amps=u*1e-6
    p=call([sys.executable,str(build_script),state,str(amps)],OUT/f"{state}_build.log")
    src=SCAN/f"7330744_PhotoRelay_V6_SIM_{state}.ms14"
    if not src.exists(): raise RuntimeError(f"builder did not create {src}")
    dst=OUT/f"7330744_PhotoRelay_V6_SIM_{state.upper()}.ms14"
    shutil.copy2(src,dst)
    csvdir=OUT/"CSV"/state
    sim=call([sys.executable,"-m","multisimforge","sim",str(dst),"--nets",",".join(nets),"--tran","1,10000","--csv",str(csvdir)],OUT/f"{state}_sim.json.txt")
    payload=json.loads((sim.stdout or "").strip())
    if payload.get("failures") or payload.get("missing") or payload.get("status") in ("FAIL","ERROR"):
        raise RuntimeError(f"Multisim simulation failed for {state}: {payload}")
    tran=csvdir/"tran.csv"
    m=tail_metrics(tran)
    rec={"state":state,"label_ru":labels[state],"photocurrent_uA":u,"simulator":payload,"measurements":m}
    summary.append(rec)
    # 1 second GUI run for reproducible real Multisim capture.
    call([sys.executable,"-m","multisimforge","set-sim-time",str(dst),"1"],OUT/f"{state}_settime.txt")
    call([sys.executable,"-m","multisimforge","preview",str(dst),str(OUT/f"Multisim_{state}_schematic.png")],OUT/f"{state}_preview.txt")

# Flat CSV with values used in the report. No values are copied from earlier versions.
with open(OUT/"7330744_stage3_real_measurements.csv","w",newline="",encoding="utf-8-sig") as f:
    w=csv.writer(f)
    w.writerow(["режим","I_PH, мкА","SENS mean, V","SENS rms, V","U_CTRL mean, V","DRV mean, V","DRV rms, V","SW rms, V","нагрузка rms, V"])
    for r in summary:
        m=r["measurements"]
        w.writerow([r["label_ru"],r["photocurrent_uA"],m["sens"]["mean_V"],m["sens"]["rms_V"],m["u_ctrl"]["mean_V"],m["drv"]["mean_V"],m["drv"]["rms_V"],m["sw"]["rms_V"],m["load"]["rms_V"]])
(OUT/"7330744_stage3_real_measurements.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
(OUT/"7330744_stage3_notes.txt").write_text(
    "Этап 3. Моделируемая версия варианта 6.\n"
    "Все численные значения в таблице получены из transient CSV движка NI Multisim 14.3 в этом прогоне.\n"
    "Ранее использованные значения узлов (в т.ч. 1.998 В и 10.5 В) не переносились.\n"
    "Освещенность моделируется обратным фототоком I_PH, включенным параллельно ФД320.\n"
    "SIM-only: C1=47 нФ, C2=1 мкФ, C3=47 нФ; отдельное питание U_CTRL=12 В через 100 Ом; сеть 220 В RMS/50 Гц через 10 Ом; тестовая нагрузка 2.2 кОм.\n"
    "Назначение D/S MOSFET выбрано только для Multisim, поскольку исходная схема отмечает затворы, но не D/S.\n",
    encoding="utf-8")
print(json.dumps({"states":states,"summary":summary},ensure_ascii=False,indent=2))
