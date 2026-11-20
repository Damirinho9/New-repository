#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Strict native KOMPAS v25 acceptance for the supplied Work 5 variant 16 package.

Runs against the exact legacy 13 M3D + 1 A3D set. No geometry is regenerated.
PASS requires native open/rebuild/save/close/reopen/rebuild, resolved relative
dependencies, expected component composition, real 3D mates, a cylinder-only
axial motion probe with stationary rod, restoration, and final reopen/rebuild.
"""
from __future__ import annotations
from pathlib import Path
import hashlib, json, math, os, re, sys, zipfile

BIN=os.environ.get("KOMPAS_BIN","/opt/ascon/kompas3d-v25/Bin")
sys.path.insert(0,BIN)
import ksapi
from constants import constants

EXPECTED={
"05_Bolt_T_paza.m3d",
"05_Gaika_Nizhnyaya.m3d",
"05_Gaika_Regulirovochnaya.m3d",
"05_Gaika_Verhnyaya.m3d",
"05_Gidrocilindr.m3d",
"05_Opora.m3d",
"05_Osnovanie.m3d",
"05_Prizhim.m3d",
"05_Pruzhina.m3d",
"05_Shaiba_Konicheskaya.m3d",
"05_Shaiba_Sfericheskaya.m3d",
"05_Shtok_Porshen.m3d",
"05_Zagotovka_Primer.m3d",
}
ASSEMBLY="05_Zazhim_Orgstankinprom_Variant_16.a3d"

def req(v,msg):
    if not v: raise RuntimeError(msg)
    return v

def sha256(p:Path):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def close(doc):
    req(doc.Close(constants.kdDoNotSaveChanges),"Close failed")

def rebuild_3d(base,label):
    d3=req(ksapi.IKompasDocument3D(base),f"{label}: cast IKompasDocument3D")
    req(d3.RebuildDocument(),f"{label}: RebuildDocument")
    top=req(d3.GetTopPart(),f"{label}: GetTopPart")
    req(top.RebuildModel(False),f"{label}: RebuildModel")
    return d3,top

def open_rebuild_save_reopen(docs,p:Path,lines):
    base=req(docs.Open(str(p),False,False),f"{p.name}: Open")
    d3,top=rebuild_3d(base,p.name)
    mass=float(top.GetMass())
    if p.suffix.lower()==".m3d":
        req(math.isfinite(mass) and mass>0.0,f"{p.name}: invalid mass {mass}")
        req(d3.GetLastFeature(),f"{p.name}: no persisted feature")
    req(base.Save(),f"{p.name}: Save")
    close(base)
    base2=req(docs.Open(str(p),False,False),f"{p.name}: Reopen")
    d32,top2=rebuild_3d(base2,p.name+" reopen")
    if p.suffix.lower()==".m3d":
        req(d32.GetLastFeature(),f"{p.name}: no feature after reopen")
        m2=float(top2.GetMass())
        req(math.isfinite(m2) and m2>0.0,f"{p.name}: invalid reopen mass")
    close(base2)
    lines.append(f"OPEN_REBUILD_SAVE_CLOSE_REOPEN_REBUILD_PASS {p.name}")

def source_paths(a3d:Path):
    req(zipfile.is_zipfile(a3d),"A3D is not a native KOMPAS ZIP container")
    with zipfile.ZipFile(a3d) as z:
        data=z.read("Sources")
    marker="<path>".encode("utf-16le")
    i=data.find(marker)
    req(i>=0,"A3D Sources path table missing")
    s=data[i:].decode("utf-16le","ignore")
    return re.findall(r"<path>([^<]+)</path>",s)

def components(top):
    parts=req(top.GetParts(),"assembly GetParts")
    out={}
    for i in range(parts.GetCount()):
        p=req(parts.GetPart(i),f"assembly part {i}")
        name=Path(p.GetFileName()).name
        out.setdefault(name,[]).append(p)
    return out

def origin(part):
    pl=req(part.GetPlacement(),"GetPlacement")
    ok,x,y,z=pl.GetOrigin(0.0,0.0,0.0)
    req(ok,"GetOrigin")
    return (float(x),float(y),float(z))

def set_origin(part,xyz):
    pl=req(part.GetPlacement(),"GetPlacement for move")
    req(pl.SetOrigin(*map(float,xyz)),"SetOrigin")
    req(part.UpdatePlacement(False),"UpdatePlacement")

def dist(a,b):
    return math.sqrt(sum((x-y)**2 for x,y in zip(a,b)))

def motion_probe(d3,top,cylinder,rod,lines):
    c0=origin(cylinder); r0=origin(rod)
    candidates=[]
    for axis in range(3):
        for sign in (-1.0,1.0):
            trial=list(c0); trial[axis]+=sign*10.0
            try:
                set_origin(cylinder,trial)
                req(top.RebuildModel(False),"motion RebuildModel")
                req(d3.RebuildDocument(),"motion RebuildDocument")
                c1=origin(cylinder); r1=origin(rod)
                cmove=dist(c1,c0); rmove=dist(r1,r0)
                candidates.append((cmove,rmove,axis,sign,c1,r1))
            except Exception:
                pass
            finally:
                try:
                    set_origin(cylinder,c0)
                    top.RebuildModel(False); d3.RebuildDocument()
                except Exception:
                    pass
    good=[x for x in candidates if x[0]>5.0 and x[1]<1e-4]
    req(good,f"No allowed cylinder-only axial motion found; probes={candidates!r}")
    best=max(good,key=lambda x:x[0])
    cmove,rmove,axis,sign,c1,r1=best
    lines.append(f"CYLINDER_MOTION_AXIS={axis} SIGN={sign:+.0f} MOVE={cmove:.6f}")
    lines.append(f"ROD_REACTION_MOVE={rmove:.9f}")
    lines.append("CYLINDER_BODY_MOTION_ROD_STATIONARY_PASS")
    req(dist(origin(cylinder),c0)<1e-4,"cylinder restore failed")
    req(dist(origin(rod),r0)<1e-4,"rod restore failed")

def main():
    if len(sys.argv)<2:
        raise SystemExit("usage: verify_work5_existing.py SOURCE_DIR [OUT_DIR]")
    root=Path(sys.argv[1]).resolve()
    out=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else root/"native_acceptance"
    out.mkdir(parents=True,exist_ok=True)
    lines=[]

    a3d=root/ASSEMBLY
    req(a3d.is_file(),"assembly missing")
    for n in EXPECTED: req((root/n).is_file(),f"missing {n}")

    src=source_paths(a3d)
    req(set(src)==EXPECTED,f"A3D dependencies mismatch: {src!r}")
    req(all("/" not in x and "\\" not in x and ":" not in x for x in src),
        f"A3D dependency is not relative: {src!r}")
    lines.append("A3D_RELATIVE_DEPENDENCIES_PASS")

    app=req(ksapi.OpenKompasInvisible(),"OpenKompasInvisible failed")
    try:
        try: app.SetHideMessage(constants.ksHideMessageYes)
        except Exception: pass
        ma,mi,re,bu=app.GetSystemVersion(0,0,0,0)
        lines.append(f"KOMPAS_VERSION={ma}.{mi}.{re} BUILD={bu}")
        lm=app.GetApplicationLicenseManager()
        if lm:
            lines.append(f"KOMPAS_VARIANT={lm.GetKompasVariant()}")
            lines.append(f"KOMPAS_3D_ACTIVE={int(bool(lm.IsKompasModuleActive(constants.ksKompasModule3D)))}")
        docs=req(app.GetDocuments(),"GetDocuments")

        for name in sorted(EXPECTED):
            open_rebuild_save_reopen(docs,root/name,lines)

        base=req(docs.Open(str(a3d),False,False),"assembly Open")
        d3,top=rebuild_3d(base,"assembly")
        comp=components(top)
        req(set(comp)==EXPECTED,f"assembly component names mismatch: {sorted(comp)}")
        req(all(len(comp[n])==1 for n in EXPECTED),"duplicate/missing assembly components")
        lines.append("POSITIONS_1_TO_10_COMPONENT_SET_PASS")

        mates=req(top.GetMateConstraints(),"GetMateConstraints")
        mate_count=int(mates.GetCount())
        lines.append(f"MATE_CONSTRAINT_COUNT={mate_count}")
        req(mate_count>0,"assembly has no real 3D mate constraints")
        lines.append("REAL_3D_MATES_PASS")

        cylinder=comp["05_Gidrocilindr.m3d"][0]
        rod=comp["05_Shtok_Porshen.m3d"][0]
        motion_probe(d3,top,cylinder,rod,lines)

        req(base.Save(),"assembly Save after restored motion probe")
        close(base)
        base2=req(docs.Open(str(a3d),False,False),"assembly final Reopen")
        d32,top2=rebuild_3d(base2,"assembly final reopen")
        comp2=components(top2)
        req(set(comp2)==EXPECTED,"final reopen component set drift")
        mates2=req(top2.GetMateConstraints(),"final GetMateConstraints")
        req(int(mates2.GetCount())==mate_count,"mate count drift after save/reopen")
        close(base2)
        lines.append("FINAL_SAVE_CLOSE_REOPEN_REBUILD_PASS")

        for p in sorted([root/n for n in EXPECTED]+[a3d]):
            lines.append(f"SHA256 {p.name} {sha256(p)}")
        lines.append("RESULT=PASS_NATIVE_WORK5_VARIANT16_ORGSTANKINPROM")
        (out/"verification.txt").write_text("\n".join(lines)+"\n",encoding="utf-8")
        (out/"verification.json").write_text(json.dumps({
            "work":5,"variant":16,"result":"PASS_NATIVE_WORK5_VARIANT16_ORGSTANKINPROM",
            "kompas_version":f"{ma}.{mi}.{re}","build":bu,"mate_count":mate_count,
            "files":{p.name:sha256(p) for p in sorted([root/n for n in EXPECTED]+[a3d])}
        },ensure_ascii=False,indent=2),encoding="utf-8")
        print((out/"verification.txt").read_text(encoding="utf-8"),end="")
    finally:
        try: app.Quit()
        except Exception: pass

if __name__=="__main__":
    try: main()
    except Exception as e:
        print("RESULT=FAIL_NATIVE_WORK5_VARIANT16_ORGSTANKINPROM",file=sys.stderr)
        print(repr(e),file=sys.stderr)
        raise
