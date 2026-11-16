from pathlib import Path
import hashlib, json, os, sys
from multisimforge import xmlio, builder

path = Path(sys.argv[1]).resolve()
root = xmlio.load(path)

components = {}
component_ids = {}
symbols = {}
models = {}

for item in root.iter("Item"):
    cls = item.get("Class")
    if cls == "CiComponent":
        comp = item.find("CiComponent")
        if comp is not None:
            ref = xmlio.unasc(comp.get("LocalName") or "")
            components[ref] = comp
            component_ids[ref] = item.get("CiID")
    elif cls == "CIITSymbolComp":
        sym = item.find("CIITSymbolComp")
        if sym is not None:
            symbols[sym.get("CiComponent")] = sym
    elif cls == "CiModel":
        model = item.find("CiModel")
        if model is not None:
            models[item.get("CiID")] = model

labels = {
    "R1": "МЛТ 4.7 МОм",
    "R2": "МЛТ 47 кОм",
    "VD1": "ФД320\nэкв. DIODE + I_PH",
    "C1": "К50-35\nSIM 0.47 мкФ; в источнике C не задана",
    "C2": "К73\nSIM 0.1 мкФ; в источнике C не задана",
    "VT1": "КП501А\nэкв. IRFD110 (N-MOS)",
    "R3": "МЛТ 330 Ом",
    "R4": "МЛТ 10 кОм",
    "VT2": "КП501А\nэкв. IRFD110 (N-MOS)",
    "VD2": "КС512А 12 В\nэкв. DIODE с BV=12 В",
    "R5": "МЛТ 5.1 кОм",
    "VT3": "КП707В2\nэкв. IRFD110 (N-MOS, sim)",
    "R6": "МЛТ 51 Ом",
    "HL1": "L383SRWT\nэкв. LED_red",
    "VD3": "КД243Ж\nэкв. 1N4003G",
    "RU1": "FNR-20K391\nэкв. 10 МОм в нормальном режиме",
    "R7": "МЛТ 58 кОм",
    "VS1": "Т123-250\nэкв. SCR",
    "R8": "МЛТ 56 Ом",
    "VD4": "КД243Ж\nэкв. 1N4003G; A=COM в sim",
    "FU1": "103, 32 А\nэкв. 1 мОм (исправный предохранитель)",
    "VD6": "RB154\nэкв. 1B4B42",
    "VD5": "КД243Ж\nэкв. 1N4003G",
    "R9": "МЛТ 56 Ом",
    "VS2": "Т123-250\nэкв. SCR",
    "C3": "К73\nSIM 0.047 мкФ; в источнике C не задана",
    "FU2": "103, 32 А\nэкв. 1 мОм (исправный предохранитель)",
    "XP1": "МРН-5Ш\nэкв. HDR1X4: 4 электрические линии; CASE вне модели",
    "VMAINS": "TEST BENCH\n~220 В RMS, 50 Гц",
    "RLOAD": "TEST LOAD\n1 кОм",
    "IPH": "TEST LIGHT\nI_PH = 2 мкА",
    "XSC1": "OSCILLOSCOPE\nCH A=U_CTRL; CH B=SW",
}

# Set fuse normal-state resistance in the actual simulation model.
for ref in ("FU1", "FU2"):
    comp = components.get(ref)
    if comp is None:
        raise RuntimeError(f"{ref} missing")
    builder._set_param(comp, 1, 1e-3, display="1m")

# Make VD2 an actual 12 V zener model instead of an ordinary diode.
vd2 = components.get("VD2")
if vd2 is None:
    raise RuntimeError("VD2 missing")
mid = vd2.get("Model")
model = models.get(mid)
if model is None:
    raise RuntimeError("VD2 model missing")
mname = xmlio.unasc(model.get("LocalName") or "")
card = next(model.iter("CiaCString"), None)
if card is None:
    raise RuntimeError("VD2 model card missing")
card.set("String", xmlio.asc(f".model {mname} D(IS=1e-12 N=1.5 RS=5 BV=12 IBV=5m)"))
model.set("ChangedByUser", "1")

# Replace on-sheet value text with source component + declared Multisim equivalent.
applied = {}
for ref, text_value in labels.items():
    comp = components.get(ref)
    if comp is None:
        continue
    cid = component_ids[ref]
    sym = symbols.get(cid)
    if sym is None:
        continue
    value = sym.find("./Objects/Item/CIITSymTextCompValue")
    if value is not None:
        value.set("Output", xmlio.uni(text_value))
        value.set("Hidden", "0")
        value.set("Font-Height", "-10")
        applied[ref] = text_value

# Force exact visible names for all source positions and test bench objects.
for ref in labels:
    comp = components.get(ref)
    if comp is None:
        continue
    sym = symbols.get(component_ids[ref])
    if sym is None:
        continue
    name = sym.find("./Objects/Item/CIITSymTextCompName")
    if name is not None:
        name.set("Output", xmlio.asc(ref))
        name.set("Hidden", "0")

tmp = path.with_name(path.stem + "_post.tmp")
xmlio.save(root, tmp, compress=True)
os.replace(tmp, path)
sha = hashlib.sha256(path.read_bytes()).hexdigest()
(Path(path.parent) / "postprocess_v6.json").write_text(json.dumps({
    "labels_applied": applied,
    "fuses_ohm": 0.001,
    "vd2_zener_bv_v": 12.0,
    "sha256_after_postprocess": sha
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps({"path": str(path), "sha256": sha, "labels": len(applied)}, ensure_ascii=False))
