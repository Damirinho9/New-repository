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
 "kp501":pick("VOLTAGE_CONTROLLED_SPST_BOUNCE"),
 "kp707":pick("BUZ90","IRFD110","2N6659"),
 "zener12":pick("1N4742A","DIODE_RATED"),
 "rectifier":pick("1N4007","MUR1510G","1N4003G","1N4001"),
 "scr":pick("2N6509","BT151_500R","SCR"),
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
 "C1 sens 0 47n CAP_ELECTROLIT_VIRTUAL",
 "C2 u_ctrl 0 1u CAP_ELECTROLIT_VIRTUAL",
 named("VT1",models["kp501"],ctrlp="g12",ctrln="sens",sw1="t1",sw2="sens"),
 "R3 g12 0 330",
 "R4 u_ctrl t1 10k",
 named("VT2",models["kp501"],ctrlp="g12",ctrln="t1",sw1="t2",sw2="t1"),
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
    net.append(named("VD6",models["bridge"],**{"AC1":"br_a","AC2":"0","V+":"g1","V-":"g2"}))
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
 "V2 vctrl 0 12",
 "RCTRL vctrl u_ctrl 100",
 "RLINE ac_src l 10",
 "RLOAD l sw 220",
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
 "XXP1":[1908,306,90],
 "I1":[270,486,90],"V1":[1908,648,90],"V2":[72,90,90],"RCTRL":[198,90],"RLINE":[1800,648],"RLOAD":[1800,144,90],
 "XSC1":[900,720],
 "GND":[[72,144],[252,558],[432,558],[666,558],[900,558],[1080,558],[1233,558],[1404,648],[1512,648],[270,558],[900,810]],
}
spec={
 "netlist":"\n".join(net)+"\n",
 "output":str(TARGET),
 "layout":layout,
 "net_names":True,
 "wire_width":2,
 "sheet":[21.0,9.5],
 "instruments":{"XSC1":{"timebase":"10ms","a_scale":"10V","b_scale":"200V","trigger":"none"}},
 "sim_time":"250ms",
 "colors":{"sens":"red","sw":"blue"}
}
res=builder.build(spec,lib=lib,allow_fallback=True,auto_repair=True)

# Patch the two KP501A simulation equivalents before any screenshots/results are made.
# The source drawing specifies the gate but does not specify an intrinsic body diode.
# Generic imported N-MOS models force body-diode current through the cascade even when "off".
# Use Multisim's native 4-terminal voltage-controlled switch symbol/model container and
# replace only its internal behavioral body with a VGS-controlled, diode-free switch.
root=xmlio.load(TARGET)
comp_ref={}
comp_by_ref={}
for item in root.iter("Item"):
    if item.get("Class")=="CiComponent" and len(item):
        ref=xmlio.text(item[0].get("LocalName") or "").strip()
        comp_ref[item.get("CiID")]=ref
        comp_by_ref[ref]=item[0]

kp501_body="""Ectrl ctrl 0 in+ in- 1
S1 sw1 sw2 ctrl 0 vsw0
.model vsw0 vswitch(Roff=1e9 Ron=10 Voff=0.9 Von=1.0)
"""
kp501_patched=[]
for ref in ("VT1","VT2"):
    comp=comp_by_ref.get(ref)
    if comp is None:
        raise RuntimeError(f"{ref}: behavioral KP501A component missing")
    hits=0
    for plist in comp.iter("CiaParamList"):
        strings=plist.find("strings")
        if strings is None:
            continue
        for entry in strings:
            raw=xmlio.text(entry.get("Value") or "")
            if "Ebounce" in raw or "triggered_pwl" in raw or "SWBOUNCE" in raw:
                entry.set("Value",xmlio.asc(kp501_body))
                hits+=1
    if hits!=1:
        raise RuntimeError(f"{ref}: expected one native switch model body, patched {hits}")
    kp501_patched.append(ref)
labels={
 "VD1":f"FD320 -> {models['photo']} + I_PH",
 "C1":"K50-35 | SIM-only 47 nF",
 "C2":"K73 | SIM-only 1 uF",
 "C3":"K73 | SIM-only 47 nF",
 "VT1":"KP501A -> native VGS switch | SIM: VON=1.0V Ron=10Ω no body diode",
 "VT2":"KP501A -> native VGS switch | SIM: VON=1.0V Ron=10Ω no body diode",
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
 "V2":"SIM CTRL SUPPLY: 12 V",
 "RCTRL":"SIM CTRL SUPPLY: 100 Ohm",
 "RLINE":"TEST BENCH: source R=10 Ohm",
 "RLOAD":"TEST LOAD: 220 Ohm (SIM-only, ~1 A RMS)",
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
 "sim_only":{"C1_F":47e-9,"C2_F":1e-6,"C3_F":47e-9,"mains_Vrms":220,"mains_Hz":50,"control_supply_V":12,"control_series_Ohm":100,"Rline_Ohm":10,"Rload_Ohm":220},
 "models":models,"kp501_behavioral":{"refs":kp501_patched,"container":models["kp501"],"Von_V":1.0,"Voff_V":0.9,"Ron_Ohm":10,"Roff_Ohm":1e9,"body_diode":False},"check":report,"sha256":hashlib.sha256(TARGET.read_bytes()).hexdigest(),"size":TARGET.stat().st_size
}
(OUT/f"{TARGET.stem}_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
(OUT/f"{TARGET.stem}_netlist.txt").write_text(spec["netlist"],encoding="utf-8")
# Geometry issues are recorded in the manifest but do not block native simulation;\n# Multisim electrical nodes remain explicit CiNode objects. Final selected states are checked again after simulation.
print(json.dumps(manifest,ensure_ascii=False,indent=2))
