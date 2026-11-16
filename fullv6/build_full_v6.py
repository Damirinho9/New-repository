import json
import hashlib
from pathlib import Path

from multisimforge import builder, check, xmlio
from multisimforge.parts import Library

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "fullv6-out"
OUT.mkdir(parents=True, exist_ok=True)
TARGET = OUT / "7330744_PhotoRelay_V6_FULL.ms14"

lib = Library()

def pick(*names):
    for name in names:
        key = lib.resolve(name)
        if key:
            return key
    raise KeyError("none of these models exists in local library: " + ", ".join(names))

models = {
    "photo": pick("PHOTO_DIODE_RATED", "PHOTODIODE", "DIODE_RATED"),
    "kp501": pick("MTD4N20E", "IRFD110", "2N6659"),
    "kp707": pick("BUZ90", "IRFD110", "2N6659"),
    "zener12": pick("1N4742A", "DIODE_RATED", "1N4003G"),
    "rectifier": pick("1N4007", "MUR1510G", "1N4003G", "1N4001"),
    "scr": pick("SCR"),
    "bridge": pick("MDA2504", "1B4B42", "3N246"),
    "fuse": pick("30_AMP", "FUSE_RATED", "RESISTOR_VIRTUAL"),
    "led": pick("LED_red", "LED_RED_RATED", "LED"),
    "header5": lib.resolve("HDR1X5") or lib.resolve("HDR1X4"),
    "cap_elec": pick("CAP_ELECTROLIT_VIRTUAL", "CAPACITOR_VIRTUAL"),
    "cap": pick("CAPACITOR_VIRTUAL"),
}
if not models["header5"]:
    raise KeyError("No 5- or 4-pin header model available")

def xline(ref, nets, model):
    return "X" + ref + " " + " ".join(nets) + " " + model

def named(ref, model, **pin_net):
    return "X" + ref + " " + model + " " + " ".join(f"{p}={n}" for p, n in pin_net.items())

net = [
    "R1 u_ctrl n_r1 4.7meg",
    "R2 n_r1 sens 47k",
    named("VD1", models["photo"], A="0", K="sens"),
    xline("C1", ["sens", "0"], models["cap_elec"]),
    xline("C2", ["u_ctrl", "0"], models["cap"]),
    named("VT1", models["kp501"], D="sens", G="g12", S="t1"),
    "R3 g12 0 330",
    "R4 u_ctrl t1 10k",
    named("VT2", models["kp501"], D="t1", G="g12", S="t2"),
    named("VD2", models["zener12"], A="0", K="u_ctrl"),
    "R5 u_ctrl t2 5.1k",
    named("VT3", models["kp707"], D="t2", G="0", S="vt3_r6"),
    "R6 vt3_r6 drv 51",
    named("HL1", models["led"], A="led_a", K="u_ctrl"),
    named("VD3", models["rectifier"], A="led_r", K="led_a"),
    "RU1 drv 0 10meg",
    "R7 led_r l 58k",
    named("VS1", models["scr"], A="sw", K="0", G="g1"),
    "R8 g1 0 56",
    named("VD4", models["rectifier"], A="0", K="g1"),
    xline("FU1", ["drv", "br_a"], models["fuse"]),
]

bridge_pins = set(lib.index[models["bridge"]]["pins"])
if {"V+", "V-", "AC1", "AC2"} <= bridge_pins:
    net.append(named("VD6", models["bridge"], **{"V+": "br_a", "V-": "0", "AC1": "g1", "AC2": "g2"}))
else:
    pins = lib.index[models["bridge"]]["pins"]
    if len(pins) != 4:
        raise RuntimeError(f"bridge {models['bridge']} has unsupported pins {pins}")
    net.append(xline("VD6", ["br_a", "g1", "0", "g2"], models["bridge"]))

net += [
    named("VD5", models["rectifier"], A="sw", K="g2"),
    "R9 g2 sw 56",
    named("VS2", models["scr"], A="0", K="sw", G="g2"),
    xline("C3", ["l", "0"], models["cap"]),
    xline("FU2", ["0", "n"], models["fuse"]),
]

header_pins = lib.index[models["header5"]]["pins"]
if set(["P1", "P2", "P3", "P4", "P5"]) <= set(header_pins):
    net.append(named("XP1", models["header5"], P1="sw", P2="l", P3="l", P4="n", P5="case"))
else:
    net.append(named("XP1", models["header5"], P1="sw", P2="l", P3="l", P4="n"))

layout = {
    "R1": [144, 180, 90],
    "R2": [144, 270, 90],
    "XVD1": [144, 378, 90],
    "XC1": [252, 378, 90],
    "XC2": [306, 180, 90],
    "XVT1": [432, 288],
    "R3": [432, 414, 90],
    "R4": [504, 180, 90],
    "XVT2": [576, 288],
    "XVD2": [666, 180, 90],
    "R5": [720, 234, 90],
    "XVT3": [756, 378],
    "R6": [846, 342],
    "XHL1": [828, 144, 90],
    "XVD3": [900, 198, 90],
    "RU1": [900, 432, 90],
    "R7": [990, 234],
    "XVS1": [1080, 414, 90],
    "R8": [1152, 486, 90],
    "XVD4": [1233, 486, 90],
    "XFU1": [1008, 324],
    "XVD6": [1197, 342],
    "XVD5": [1323, 198],
    "R9": [1323, 270],
    "XVS2": [1404, 342, 90],
    "XC3": [1512, 450, 90],
    "XFU2": [1512, 576],
    "XXP1": [1656, 306],
    "GND": [
        [252, 522], [432, 522], [666, 522], [900, 558],
        [1080, 558], [1233, 558], [1404, 558], [1512, 648]
    ],
}

spec = {
    "netlist": "\n".join(net) + "\n",
    "output": str(TARGET),
    "layout": layout,
    "net_names": True,
    "wire_width": 2,
    "sheet": [18.5, 7.5],
}

result = builder.build(spec, lib=lib, allow_fallback=True, auto_repair=True)

labels = {
    "R1": "MLT 4.7 MOhm",
    "R2": "MLT 47 kOhm",
    "VD1": f"FD320 -> {models['photo']}",
    "C1": "K50-35; C not specified in source",
    "C2": "K73; C not specified in source",
    "VT1": f"KP501A -> {models['kp501']}",
    "R3": "MLT 330 Ohm",
    "R4": "MLT 10 kOhm",
    "VT2": f"KP501A -> {models['kp501']}",
    "VD2": f"KS512A 12V -> {models['zener12']}",
    "R5": "MLT 5.1 kOhm",
    "VT3": f"KP707V2 -> {models['kp707']}",
    "R6": "MLT 51 Ohm",
    "HL1": f"L383SRWT -> {models['led']}",
    "VD3": f"KD243Zh -> {models['rectifier']}",
    "RU1": "FNR-20K391 -> 10M normal-state proxy",
    "R7": "MLT 58 kOhm",
    "VS1": f"T123-250 -> {models['scr']}",
    "R8": "MLT 56 Ohm",
    "VD4": f"KD243Zh -> {models['rectifier']} (A/K model assignment)",
    "FU1": f"Fuse 103 32A -> {models['fuse']}",
    "VD6": f"RB154 -> {models['bridge']} (pin mapping model-only)",
    "VD5": f"KD243Zh -> {models['rectifier']}",
    "R9": "MLT 56 Ohm",
    "VS2": f"T123-250 -> {models['scr']}",
    "C3": "K73; C not specified in source",
    "FU2": f"Fuse 103 32A -> {models['fuse']}",
    "XP1": f"MRN-5Sh -> {models['header5']}",
}

root = xmlio.load(TARGET)
patched = []

# Bind visible labels to actual component LocalName. Harvested database symbols
# sometimes retain their source A-section label; that must not leak into the final drawing.
comp_ref = {}
for item in root.iter("Item"):
    if item.get("Class") == "CiComponent" and len(item):
        cid = item.get("CiID")
        if cid:
            comp_ref[cid] = xmlio.text(item[0].get("LocalName") or "").strip()

for item in root.iter("Item"):
    if item.get("Class") != "CIITSymbolComp" or not len(item):
        continue
    sym = item[0]
    ref = comp_ref.get(sym.get("CiComponent") or "", "")
    if not ref or ref == "0":
        continue
    for name_el in sym.findall(".//CIITSymTextCompName"):
        name_el.set("Output", xmlio.uni(ref))
    value_els = sym.findall(".//CIITSymTextCompValue")
    if ref in {"C1", "C2", "C3"}:
        for value_el in value_els:
            value_el.set("Hidden", "1")
    elif ref in labels:
        for value_el in value_els:
            value_el.set("Output", xmlio.uni(labels[ref]))
        patched.append(ref)

xmlio.save(root, TARGET, compress=True)

report = check.check_file(TARGET)
manifest = {
    "source": "Variant 6 photo relay, method sheet pp.49-50",
    "positions": 27,
    "models": models,
    "varistor_model_note": "FNR-20K391 represented by 10 MOhm normal-state proxy in this structural stage; native V430MA7B ReplaceComponent crashed in Multisim 14.3.",
    "patched_labels": sorted(patched),
    "bridge_model_mapping": {"V+": "BR_A", "V-": "0", "AC1": "G1", "AC2": "G2"},
    "mos_model_ds_assignment": {
        "VT1": {"D": "SENS", "S": "T1", "G": "G12"},
        "VT2": {"D": "T1", "S": "T2", "G": "G12"},
        "VT3": {"D": "T2", "S": "VT3_R6", "G": "0"},
    },
    "source_ambiguities_preserved": [
        "C1/C2/C3 capacitances are not specified in the source and their visible value labels are hidden.",
        "The source marks MOSFET gates but not D/S; D/S assignment above is for the Multisim model only.",
        "The source does not mark RB154 +/-/~ pins; bridge pin mapping above is for the Multisim model only.",
        "VD4 polarity is not marked in the source; model uses A=0, K=G1.",
    ],
    "builder_result": {k: v for k, v in result.items() if k not in ("expected",)},
    "check": report,
    "sha256": hashlib.sha256(TARGET.read_bytes()).hexdigest(),
    "size_bytes": TARGET.stat().st_size,
}
(OUT / "7330744_FULL_V6_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
(OUT / "7330744_FULL_V6_netlist.txt").write_text(spec["netlist"], encoding="utf-8")

if report.get("problems"):
    raise SystemExit("Connectivity check failed: " + json.dumps(report["problems"], ensure_ascii=False))

print(json.dumps({
    "ms14": str(TARGET),
    "size": TARGET.stat().st_size,
    "sha256": manifest["sha256"],
    "models": models,
    "warnings": report.get("warnings", []),
    "status": "PASS" if not report.get("problems") else "FAIL",
}, ensure_ascii=False, indent=2))
