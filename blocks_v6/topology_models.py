"""Preserve native pin templates and record model substitutions. Do not mark proxy models as exact."""
import re,os
from pathlib import Path
from stage3_model_patch import _find_component,_find_model,_cards,_validate,_relative,_mos

def vendor_card(path,alias,expected):
    raw=Path(path).read_text(encoding="latin1")
    lines=raw.splitlines()
    idx=next(i for i,l in enumerate(lines) if re.match(r"(?i)^\s*\.subckt\s+\S+",l))
    fields=lines[idx].split()
    if len(fields)!=5 or fields[1].lower() not in ({"irfbe30","sihfbe30"} if expected=="SIHFBE30" else {expected.lower()}):
        raise ValueError("Unexpected vendor subcircuit signature "+repr(fields))
    # Diodes' published pin order is 3/4/5 = D/G/S.
    # For Vishay require an explicit D/G/S declaration, do not guess by file name.
    if expected=="ZVN2120G":
        if fields[2:]!=["3","4","5"] or not any(re.search(r"\bD\s+G\s+S\b",l) for l in lines[idx+1:idx+5]):
            raise ValueError("ZVN2120G pin order not confirmed")
    else:
        context="\n".join(lines[max(0,idx-15):idx+30])
        if not (re.search(r"(?i)\bdrain\b[\s,;:/-]+\bgate\b[\s,;:/-]+\bsource\b",context)
                or re.search(r"(?i)(?:\*|;)\s*D\s+G\s+S\b",context)
                or all(re.search(r"(?im)^\*\s*Node\s+"+str(i)+r"\s*->\s*"+n+r"\b",context) for i,n in [(1,"Drain"),(2,"Gate"),(3,"Source")])
                or [x.lower() for x in fields[2:]]==["d","g","s"]):
            raise ValueError("Vishay pin order not explicitly confirmed")
    # Rename the outer model only, leave the manufacturer body and copyright text intact.
    original=fields[1]
    header=".SUBCKT "+alias+" "+" ".join(fields[2:])
    tail=lines[idx+1:]
    ends=[i for i,l in enumerate(tail) if re.match(r"(?i)^\s*\.ends(?:\s+"+re.escape(original)+r")?\s*$",l)]
    if len(ends)!=1:raise ValueError("Unexpected vendor subcircuit endings")
    tail[ends[0]]=".ENDS "+alias
    return "\n".join([header]+[l for l in lines[:idx] if not l.strip() or l.lstrip().startswith("*")]+tail[:ends[0]+1])



def _find_any_card(comp,model,xmlio):
    ma=next((e for e in model.iter("CiaCString") if ".model" in xmlio.text(e.get("String") or "").lower() or ".subckt" in xmlio.text(e.get("String") or "").lower()),None)
    cb=next((e for e in comp.findall("./Attributes/Item/CiaCollString/strings/Item") if ".model" in xmlio.text(e.get("Value") or "").lower() or ".subckt" in xmlio.text(e.get("Value") or "").lower()),None)
    if ma is None or cb is None: raise RuntimeError("SPICE card not found")
    return ma,cb

def _fd320_card(old):
    s=chr(10).join(old.splitlines())
    mm=re.search("(?i)[.]model[ \\t]+([^ \\t]+)",s)
    if mm:
        name=mm.group(1)
        return f".MODEL {name} D(IS=2n N=1.25 RS=2 CJO=80p VJ=0.65 M=0.45 BV=30 IBV=50u TT=1u)"
    sm=re.search("(?im)^[ \\t]*[.]subckt[ \\t]+([^ \\t]+)[ \\t]+([^ \\t]+)[ \\t]+([^ \\t]+)",s)
    if not sm:
        raise RuntimeError("Unsupported FD320 carrier card")
    name,p1,p2=sm.groups()
    return chr(10).join([
        f".SUBCKT {name} {p1} {p2}",
        f"DPHOTO {p1} {p2} DFD320",
        ".MODEL DFD320 D(IS=2n N=1.25 RS=2 CJO=80p VJ=0.65 M=0.45 BV=30 IBV=50u TT=1u)",
        f".ENDS {name}",
    ])

def _patch_fd320(root,xmlio,notes):
    c=_find_component(root,xmlio,"VD1");mod=_find_model(root,c);a,b=_find_any_card(c,mod,xmlio)
    sa=_fd320_card(xmlio.text(a.get("String") or "")); sb=_fd320_card(xmlio.text(b.get("Value") or ""))
    a.set("String",xmlio.asc(sa));b.set("Value",xmlio.asc(sb));mod.set("ChangedByUser","1")
    notes["VD1"]="FD320 bounded model: IS=2nA, Cj=80pF, BV=30V; external I_PH is photocurrent. Source data: dark current <=50nA at ~10-12V."

def patch_models(root,xmlio,refs=None):
    notes={}
    refs=set(refs or ("VT1","VT2","VT3","VS1","VS2","VD1","VD3","VD4","VD5"))
    for ref in ("VT1","VT2","VT3","VS1","VS2"):
        if ref not in refs:continue
        c=_find_component(root,xmlio,ref);m=_find_model(root,c);a,b=_cards(c,m,xmlio)
        x,y=xmlio.text(a.get("String")),xmlio.text(b.get("Value"))
        n1,n2=x.split()[1],y.split()[1]
        if ref.startswith("VT"):
            small=ref!="VT3"
            src="vendor/ZVN2120G.txt" if small else "vendor/SIHFBE30.lib"
            expected="ZVN2120G" if small else "SIHFBE30"
            try:
                s,t=vendor_card(src,n1,expected),vendor_card(src,n2,expected)
                notes[ref]=expected+" vendor electrical proxy"
            except (OSError,ValueError,StopIteration) as exc:
                # A fallback is explicitly an approximate diagnostic card, not an approved substitution.
                args=(1.5,0.08,2,2,220) if small else (3.2,0.55,0.8,0.8,800)
                s,t=_mos(n1,*args),_mos(n2,*args)
                notes[ref]="APPROXIMATE ONLY: "+str(exc)
        else:
            s,t=_relative(x),_relative(y)
            notes[ref]="Functional cathode-referenced NI SCR, not manufacturer T123-250"
        _validate(s);_validate(t);a.set("String",xmlio.asc(s));b.set("Value",xmlio.asc(t));m.set("ChangedByUser","1")
    if "VD1" in refs:_patch_fd320(root,xmlio,notes)
    # MUR1510G native symbol is used only as a two-terminal carrier.
    # Its original 100 V model is unsuitable for a 220 V circuit.
    for ref in ("VD3","VD4","VD5"):
        if ref not in refs:continue
        c=_find_component(root,xmlio,ref);m=_find_model(root,c)
        a=next(e for e in m.iter("CiaCString") if ".model" in xmlio.text(e.get("String") or "").lower())
        b=next(e for e in c.findall("./Attributes/Item/CiaCollString/strings/Item") if ".model" in xmlio.text(e.get("Value") or "").lower())
        for e,k in ((a,"String"),(b,"Value")):
            old=xmlio.text(e.get(k))
            name=re.search(r"(?i)\.model\s+(\S+)",old).group(1)
            e.set(k,xmlio.asc(f".MODEL {name} D(IS=1n N=1.8 RS=0.12 BV=1000 IBV=10u CJO=20p TT=2u)"))
        m.set("ChangedByUser","1")
        notes[ref]="Approximate KD243Zh 1000V/1A rectifier; not vendor fit"
    return notes

def verify_saved_cards(root,xmlio,refs=None):
    refs=set(refs or ("VT1","VT2","VT3","VS1","VS2","VD1","VD3","VD4","VD5"))
    for ref in ("VT1","VT2","VT3","VS1","VS2"):
        if ref not in refs:continue
        c=_find_component(root,xmlio,ref);m=_find_model(root,c);a,b=_cards(c,m,xmlio)
        for x in (xmlio.text(a.get("String")),xmlio.text(b.get("Value"))):
            _validate(x)
            if ref.startswith("VS") and "EGREL GREL" not in x:raise RuntimeError(ref+": gate reference lost")
    if "VD1" in refs:
        c=_find_component(root,xmlio,"VD1");mod=_find_model(root,c);a,b=_find_any_card(c,mod,xmlio)
        for x in (xmlio.text(a.get("String") or ""),xmlio.text(b.get("Value") or "")):
            if "BV=30" not in x or ("IS=2n" not in x and "IS=2N" not in x.upper()): raise RuntimeError("VD1: FD320 model patch lost")
    for ref in ("VD3","VD4","VD5"):
        if ref not in refs:continue
        c=_find_component(root,xmlio,ref);m=_find_model(root,c)
        if not any("BV=1000" in xmlio.text(e.get("String") or "") for e in m.iter("CiaCString")):raise RuntimeError(ref+": 1000V model lost")
