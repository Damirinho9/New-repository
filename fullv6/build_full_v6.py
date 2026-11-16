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
    "rectifier": pick("1N4007", "1N4003G", "1N4001"),
    "varistor": pick("V430MA7B", "SM4T220CA", "RESISTOR_VIRTUAL"),
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

net = []
# Positions 1-13: sensing and MOSFET control chain.
net += [
    "R1 u_ctrl n_r1 4.7meg",
    "R2 n_r1 sens 47k",
    named("VD1", models["photo"], A="com", K="sens"),
    xline("C1", ["sens", "com"], models["cap_elec"]),
    xline("C2", ["u_ctrl", "com"], models["cap"]),
    named("VT1", models["kp501"], D="sens", G="g12", S="t1"),
    "R3 g12 com 330",
    "R4 u_ctrl t1 10k",
    named("VT2", models["kp501"], D="t1", G="g12", S="t2"),
    named("VD2", models["zener12"], A="com", K="u_ctrl"),
    "R5 u_ctrl t2 5.1k",
    named("VT3", models["kp707"], D="t2", G="com", S="vt3_r6"),
    "R6 vt3_r6 drv 51",
]
# Positions 14-17: indicator/protection branch.
net += [
    named("HL1", models["led"], A="led_a", K="u_ctrl"),
    named("VD3", models["rectifier"], A="led_r", K="led_a"),
    xline("RU1", ["drv", "com"], models["varistor"]),
    "R7 led_r l 58k",
]
# Positions 18-27: antiparallel thyristor power stage.
net += [
    named("VS1", models["scr"], A="sw", K="com", G="g1"),
    "R8 g1 com 56",
    named("VD4", models["rectifier"], A="com", K="g1"),
    xline("FU1", ["drv", "br_a"], models["fuse"]),
]

bridge_pins = set(lib.index[models["bridge"]]["pins"])
if {"V+", "V-", "AC1", "AC2"} <= bridge_pins:
    net.append(named("VD6", models["bridge"], **{"V+": "br_a", "V-": "com", "AC1": "g1", "AC2": "g2"}))
elif {"AC1", "AC2", "V+", "V-"} <= bridge_pins:
    net.append(named("VD6", models["bridge"], **{"AC1": "g1", "AC2": "g2", "V+": "br_a", "V-": "com"}))
else:
    pins = lib.index[models["bridge"]]["pins"]
    if len(pins) != 4:
        raise RuntimeError(f"bridge {models['bridge']} has unsupported pins {pins}")
    net.append(xline("VD6", ["br_a", "g1", "com", "g2"], models["bridge"]))

net += [
    named("VD5", models["rectifier"], A="sw", K="g2"),
    "R9 g2 sw 56",
    named("VS2", models["scr"], A="com", K="sw", G="g2"),
    xline("C3", ["l", "com"], models["cap"]),
    xline("FU2", ["com", "n"], models["fuse"]),
]

# Five-contact project connector. P2 and P3 intentionally share L because the
# source drawing shows the load and mains line as one continuous conductor.
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
    "XRU1": [900, 432, 90],
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
    "GND": [[846, 630], [1458, 630]],
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

# Replace library model labels with the source type and explicit modelling substitution.
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
    "RU1": f"FNR-20K391 -> {models['varistor']}",
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
for sym in root.iter("CIITSymbolComp"):
    name_el = sym.find("./Objects/Item/CIITSymTextCompName")
    value_el = sym.find("./Objects/Item/CIITSymTextCompValue")
    if name_el is None or value_el is None:
        continue
    ref = xmlio.text(name_el.get("Output") or "").strip()
    if ref in labels:
        value_el.set("Output", xmlio.uni(labels[ref]))
        patched.append(ref)
xmlio.save(root, TARGET, compress=True)

report = check.check_file(TARGET)
manifest = {
    "source": "Variant 6 photo relay, method sheet pp.49-50",
    "positions": 27,
    "models": models,
    "patched_labels": sorted(patched),
    "bridge_model_mapping": {"V+": "BR_A", "V-": "COM", "AC1": "G1", "AC2": "G2"},
    "mos_model_ds_assignment": {
        "VT1": {"D": "SENS", "S": "T1", "G": "G12"},
        "VT2": {"D": "T1", "S": "T2", "G": "G12"},
        "VT3": {"D": "T2", "S": "VT3_R6", "G": "COM"},
    },
    "source_ambiguities_preserved": [
        "C1/C2/C3 capacitances are not specified in the source and are not claimed as source values.",
        "The source marks MOSFET gates but not D/S; D/S assignment above is for the Multisim model only.",
        "The source does not mark RB154 +/-/~ pins; bridge pin mapping above is for the Multisim model only.",
        "VD4 polarity is not marked in the source; model uses A=COM, K=G1.",
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
