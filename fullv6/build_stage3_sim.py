import json, math, sys, hashlib
from pathlib import Path
from multisimforge import builder, check, xmlio
from multisimforge.parts import Library

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"stage3-out"
OUT.mkdir(parents=True,exist_ok=True)
state=sys.argv[1] if len(sys.argv)>1 else "probe"
iph=float(sys.argv[2]) if len(sys.argv)>2 else 1e-6
TARGET=OUT/f"7330744_PhotoRelay_V6_SIM_{state}.ms14"

lib=Library()
def pick(*names):
    for name in names:
        k=lib.resolve(name)
        if k:return k
    raise KeyError("missing model: "+", ".join(names))

models={
 "photo":pick("PHOTO_DIODE_RATED","PHOTODIODE","DIODE_RATED"),
 "kp501":pick("MTD4N20E","IRFD110","2N6659"),
 "kp707":pick("BUZ90","IRFD110","2N6659"),
 "zener12":pick("1N4742A","DIODE_RATED"),
 "rectifier":pick("1N4007","MUR1510G","1N4003G","1N4001"),
 "scr":pick("SCR"),
 "bridge":pick("MDA2504","1B4B42","3N246"),
 "fuse":pick("30_AMP","FUSE_RATED","RESISTOR_VIRTUAL"),
 "led":pick("LED_red","LED_RED_RATED","LED"),
 "header5":pick("HDR1X5","HDR1X4"),
}

def named(ref,model,**pins):
    return "X"+ref+" "+model+" "+" ".join(f"{p}={n}" for p,n in pins.items())
def xline(ref,nets,model):
    return "X"+ref+" "+" ".join(nets)+" "+model

# Source topology from Variant 6. C values are simulation-only because the source page does not specify them.
net=[
 "R1 u_ctrl n_r1 4.7meg",
 "R2 n_r1 sens 47k",
 named("VD1",models["photo"],A="0",K="sens"),
 "C1 sens 0 0.47u CAP_ELECTROLIT_VIRTUAL",
 "C2 u_ctrl 0 10u CAP_ELECTROLIT_VIRTUAL",
 named("VT1",models["kp501"],D="sens",G="g12",S="t1"),
 "R3 g12 0 330",
 "R4 u_ctrl t1 10k",
 named("VT2",models["kp501"],D="t1",G="g12",S="t2"),
 named("VD2",models["zener12"],A="0",K="u_ctrl"),
 "R5 u_ctrl t2 5.1k",
 named("VT3",models["kp707"],D="t2",G="0",S="vt3_r6"),
 "R6 vt3_r6 drv 51",
 named("HL1",models["led"],A="led_a",K="u_ctrl"),
 named("VD3",models["rectifier"],A="led_r",K="led_a"),
 "RU1 drv 0 10meg",
 "R7 led_r l 58k",
 named("VS1",models["scr"],A="sw",K="0",G="g1"),
 "R8 g1 0 56",
 named("VD4",models["rectifier"],A="0",K="g1"),
 xline("FU1",["drv","br_a"],models["fuse"]),
]
bridge_pins=set(lib.index[models["bridge"]]["pins"])
if {"V+","V-","AC1","AC2"}<=bridge_pins:
    net.append(named("VD6",models["bridge"],**{"V+":"br_a","V-":"0","AC1":"g1","AC2":"g2"}))
else:
    net.append(xline("VD6",["br_a","g1","0","g2"],models["bridge"]))
net += [
 named("VD5",models["rectifier"],A="sw",K="g2"),
 "R9 g2 sw 56",
 named("VS2",models["scr"],A="0",K="sw",G="g2"),
 "C3 l 0 47n CAPACITOR_VIRTUAL",
 xline("FU2",["0","n"],models["fuse"]),
]
hp=set(lib.index[models["header5"]]["pins"])
if {"P1","P2","P3","P4","P5"}<=hp:
    net.append(named("XP1",models["header5"],P1="sw",P2="l",P3="l",P4="n",P5="0"))
else:
    net.append(named("XP1",models["header5"],P1="sw",P2="l",P3="l",P4="n"))

# Simulation-only test bench. I1 is reverse photocurrent from cathode node SENS to anode/common.
net += [
 f"I1 sens 0 {iph:.12g}",
 "V1 ac_src n SIN(0 311.1269837 50)",
 "RLINE ac_src l 10",
 "RLOAD l sw 2.2k",
 "XSC1 sens sw 0 nc_trig 0 nc_b OSCILLOSCOPE",
]

layout={
 "R1":[144,180,90],"R2":[144,270,90],"XVD1":[144,378,90],
 "C1":[252,378,90],"C2":[306,180,90],"XVT1":[432,288],
 "R3":[432,414,90],"R4":[504,180,90],"XVT2":[576,288],
 "XVD2":[666,180,90],"R5":[720,234,90],"XVT3":[756,378],
 "R6":[846,342],"XHL1":[828,144,90],"XVD3":[900,198,90],
 "RU1":[900,432,90],"R7":[990,234],"XVS1":[1080,414,90],
 "R8":[1152,486,90],"XVD4":[1233,486,90],"XFU1":[1008,324],
 "XVD6":[1197,342],"XVD5":[1323,198],"R9":[1323,270],
 "XVS2":[1404,342,90],"C3":[1512,450,90],"XFU2":[1512,576],
 "XXP1":[1656,306],
 "I1":[270,486,90],"V1":[1782,558,90],"RLINE":[1692,558],"RLOAD":[1656,144,90],
 "XSC1":[720,666],
 "GND":[[252,558],[432,558],[666,558],[900,558],[1080,558],[1233,558],[1404,648],[1512,648],[270,558],[756,756]],
}
spec={
 "netlist":"\n".join(net)+"\n",
 "output":str(TARGET),
 "layout":layout,
 "net_names":True,
 "wire_width":2,
 "sheet":[19.5,9.0],
 "instruments":{"XSC1":{"timebase":"10ms","a_scale":"10V","b_scale":"200V","trigger":"none"}},
 "sim_time":"250ms",
 "colors":{"sens":"red","sw":"blue"}
}
res=builder.build(spec,lib=lib,allow_fallback=True,auto_repair=True)

# Patch visible labels so test-bench parts and SIM-only capacitor values cannot be confused with the source BOM.
root=xmlio.load(TARGET)
comp_ref={}
for item in root.iter("Item"):
    if item.get("Class")=="CiComponent" and len(item):
        comp_ref[item.get("CiID")]=xmlio.text(item[0].get("LocalName") or "").strip()
labels={
 "VD1":f"FD320 -> {models['photo']} + I_PH",
 "C1":"K50-35 | SIM-only 0.47 uF",
 "C2":"K73 | SIM-only 10 uF",
 "C3":"K73 | SIM-only 47 nF",
 "VT1":f"KP501A -> {models['kp501']}",
 "VT2":f"KP501A -> {models['kp501']}",
 "VT3":f"KP707V2 -> {models['kp707']}",
 "VD2":f"KS512A -> {models['zener12']}",
 "VD3":f"KD243Zh -> {models['rectifier']}",
 "VD4":f"KD243Zh -> {models['rectifier']}",
 "VD5":f"KD243Zh -> {models['rectifier']}",
 "VS1":"T123-250 -> SCR","VS2":"T123-250 -> SCR",
 "VD6":f"RB154 -> {models['bridge']}",
 "FU1":f"103 32A -> {models['fuse']}","FU2":f"103 32A -> {models['fuse']}",
 "I1":f"SIM LIGHT: I_PH={iph*1e6:.6g} uA",
 "V1":"TEST BENCH: 220 Vrms / 50 Hz",
 "RLINE":"TEST BENCH: source R=10 Ohm",
 "RLOAD":"TEST LOAD: 2.2 kOhm",
 "XSC1":"XSC1: A=SENS, B=SW",
}
for item in root.iter("Item"):
    if item.get("Class")!="CIITSymbolComp" or not len(item): continue
    sym=item[0]; ref=comp_ref.get(sym.get("CiComponent") or "","")
    if ref in labels:
        for el in sym.findall(".//CIITSymTextCompValue"):
            el.set("Output",xmlio.uni(labels[ref])); el.set("Hidden","0"); el.set("Font-Height","-10")
xmlio.save(root,TARGET,compress=True)

report=check.check_file(TARGET)
manifest={
 "state":state,"photocurrent_A":iph,"photocurrent_uA":iph*1e6,
 "sim_only":{"C1_F":0.47e-6,"C2_F":10e-6,"C3_F":47e-9,"mains_Vrms":220,"mains_Hz":50,"Rline_Ohm":10,"Rload_Ohm":2200},
 "models":models,"check":report,"sha256":hashlib.sha256(TARGET.read_bytes()).hexdigest(),"size":TARGET.stat().st_size
}
(OUT/f"{TARGET.stem}_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
(OUT/f"{TARGET.stem}_netlist.txt").write_text(spec["netlist"],encoding="utf-8")
if report.get("problems"): raise SystemExit(json.dumps(report["problems"],ensure_ascii=False))
print(json.dumps(manifest,ensure_ascii=False,indent=2))
