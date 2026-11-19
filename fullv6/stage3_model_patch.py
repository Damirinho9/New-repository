import os,re

def _find_component(root,xmlio,ref):
    for item in root.iter("Item"):
        if item.get("Class")=="CiComponent" and len(item) and xmlio.text(item[0].get("LocalName") or "").strip()==ref:
            return item[0]
    raise RuntimeError(ref+": component not found")

def _find_model(root,comp):
    for item in root.iter("Item"):
        if item.get("Class")=="CiModel" and item.get("CiID")==comp.get("Model") and len(item):
            return item[0]
    raise RuntimeError("Missing model")

def _cards(comp,model,xmlio):
    a=next(e for e in model.iter("CiaCString") if ".subckt" in xmlio.text(e.get("String") or "").lower())
    bs=[e for e in comp.findall("./Attributes/Item/CiaCollString/strings/Item") if ".subckt" in xmlio.text(e.get("Value") or "").lower()]
    if len(bs)!=1:raise RuntimeError("Component card count="+str(len(bs)))
    return a,bs[0]

def _mos(name,v,kp,rd,rs,bv):
    return "\n".join([f".SUBCKT {name} 1 2 3",f"RD 1 4 {rd}",f"RS 5 3 {rs}","RG 2 6 20","M1 4 6 5 5 MCORE W=100u L=100u","D1 3 1 DBODY",f".MODEL MCORE NMOS LEVEL=1 VTO={v} KP={kp} LAMBDA=0.005",f".MODEL DBODY D IS=1e-12 N=1.2 BV={bv} IBV=1m",f".ENDS {name}"])

def _relative(s):
    # Keep the native NI latch and reset logic. Only change gate measurement reference.
    if "EGREL GREL" in s:return s
    s=s.replace("\r\n","\n").replace("\r","\n")
    s,n1=re.subn(r"(?im)^(\s*xU3\.A\s+)gate(\s+)",r"\1GREL\2",s)
    s,n2=re.subn(r"(?im)^(\s*xU2\.S\s+)gate(\s+)",r"\1GREL\2",s)
    if (n1,n2)!=(1,1):raise RuntimeError("Unexpected NI SCR model receiver template")
    i=s.index("\n")
    return s[:i+1]+"EGREL GREL 0 Gate Cathode 1\n"+s[i+1:]

def _validate(s):
    if "\\n" in s or "\n" not in s or not s.lstrip().lower().startswith(".subckt"):raise RuntimeError("Invalid SPICE card")

def patch_models(root,xmlio):
    notes={}
    for ref in ("VT1","VT2","VT3","VS1","VS2"):
        c=_find_component(root,xmlio,ref);m=_find_model(root,c);a,b=_cards(c,m,xmlio)
        old=xmlio.text(a.get("String"));old2=xmlio.text(b.get("Value"))
        if ref in ("VT1","VT2","VT3"):
            v=float(os.environ.get("KP707_VTO","3.2") if ref=="VT3" else os.environ.get("KP501_VTO","1.5"))
            args=(v,0.55,0.8,0.8,800) if ref=="VT3" else (v,0.08,2,2,240)
            s=_mos(old.split()[1],*args);t=_mos(old2.split()[1],*args)
            notes[ref]="Approximate N-MOS model, not manufacturer-exact; D/G/S order; body diode retained"
        else:
            s=_relative(old);t=_relative(old2)
            v=float(os.environ.get("SCR_VTH","2.5"))
            q=c.find(".//CiaParamList");ds=q.findall("./doubles/Item");ps=q.findall("./parameters/Item")
            ds[1].set("Value",format(v,".17g"));ps[1].set("Value",xmlio.asc(f"{v:g}"))
            notes[ref]="NI functional latching SCR, cathode-referenced detector; not exact T123-250"
        _validate(s);_validate(t);a.set("String",xmlio.asc(s));b.set("Value",xmlio.asc(t));m.set("ChangedByUser","1")
    return notes

def verify_saved_cards(root,xmlio):
    for ref in ("VT1","VT2","VT3","VS1","VS2"):
        c=_find_component(root,xmlio,ref);m=_find_model(root,c);a,b=_cards(c,m,xmlio)
        for x in (xmlio.text(a.get("String")),xmlio.text(b.get("Value"))):
            _validate(x)
            if ref.startswith("VT") and ("MCORE" not in x or "DBODY" not in x):raise RuntimeError(ref+": model patch not retained")
            if ref.startswith("VS") and "EGREL GREL" not in x:raise RuntimeError(ref+": SCR patch not retained")
