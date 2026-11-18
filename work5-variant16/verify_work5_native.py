# -*- coding: utf-8 -*-
"""Strict native acceptance for Work 5 variant 16."""
from __future__ import annotations
from pathlib import Path
import json, math, re, sys, zipfile
import pythoncom
from work5_common import *
from build_work5_native import FILES, ASSEMBLY, path

REPORT=OUT/"verification.txt"

def open_model(kompas,p):
    d=require(kompas.Document3D(),f"{p.name}: Document3D")
    require(d.Open(str(p),False),f"{p.name}: Open")
    require(d.RebuildDocument(),f"{p.name}: Rebuild")
    return d

def group(doc):
    g={}
    for p in enumerate_parts(doc):
        g.setdefault(Path(part_filename(p)).name,[]).append(p)
    return g

def get_origin(part):
    pl=require(part.GetPlacement(),"GetPlacement")
    r=pl.GetOrigin()
    if isinstance(r,tuple):
        vals=list(r)
        if len(vals)>=4 and isinstance(vals[0],(bool,int)):
            vals=vals[-3:]
        if len(vals)>=3:
            return tuple(float(x) for x in vals[-3:])
    raise RuntimeError(f"Unexpected GetOrigin result for {part_filename(part)}: {r!r}")

def set_origin(part,xyz):
    pl=require(part.GetPlacement(),"GetPlacement")
    require(pl.SetOrigin(*map(float,xyz)),"SetOrigin")
    require(part.UpdatePlacement(),"UpdatePlacement")

def sources_from_a3d(p):
    with zipfile.ZipFile(p) as z:
        data=z.read("Sources")
    marker="<path>".encode("utf-16le")
    i=data.find(marker)
    require(i>=0,"A3D Sources has no path table")
    s=data[i:].decode("utf-16le","ignore")
    return re.findall(r"<path>([^<]+)</path>",s)

def main():
    pythoncom.CoInitialize()
    const=constants(); kompas=get_kompas5()
    _,val=read_params()
    all_parts=[path(k) for k in FILES]

    # Every detail must independently reopen and rebuild.
    detail_info=[]
    for p in all_parts:
        native_file(p)
        d=open_model(kompas,p)
        require(d.IsDetail(),f"{p.name}: not a detail")
        require(d.GetLastFeature(),f"{p.name}: no persisted feature")
        detail_info.append((p.name,p.stat().st_size,sha256(p)))
        try:d.close()
        except Exception:pass

    native_file(ASSEMBLY)
    src=sources_from_a3d(ASSEMBLY)
    expected={p.name for p in all_parts}
    require(set(src)==expected,f"A3D source dependency mismatch: {src!r}")
    require(all("\\" not in s and "/" not in s and ":" not in s for s in src),
            f"Dependencies are not relative basenames: {src!r}")

    asm=open_model(kompas,ASSEMBLY)
    require(not asm.IsDetail(),"A3D reopened as detail")
    g=group(asm)
    require(set(g)==expected,f"Assembly component set mismatch: {sorted(g)}")
    require(all(len(g[n])==1 for n in expected),"Duplicate/missing components")
    require(mate_count(asm)>=10,f"Too few real 3D mates: {mate_count(asm)}")

    P={k:g[FILES[k]][0] for k in FILES}
    central=("bolt","nut1","nut2","clamp","cylinder","rod","nut7","washer_c","washer_s","spring")
    origins={k:get_origin(P[k]) for k in P}

    # Figure 59r central chain must be coaxial in Y/Z.
    for k in central:
        x,y,z=origins[k]
        require(abs(y)<1e-5 and abs(z)<1e-5,f"{k} is off central axis: {origins[k]}")

    require(origins["support"][1]>0,"Support 10 must be on one side of clamp")
    require(origins["workpiece"][1]<0,"Workpiece must be on the opposite side")
    require(abs(origins["support"][0])<1e-5 and abs(origins["workpiece"][0])<1e-5,
            "Support/workpiece must rise from the table/base plane")
    require(abs(origins["clamp"][0]-val("support_height"))<1e-5,
            "Clamp bottom is not at support top level")
    require(abs(origins["clamp"][0]-val("workpiece_height"))<1e-5,
            "Clamp bottom is not at workpiece top level")

    # Source operating principle:
    # rod/piston remains stationary; cylinder body is the translating member.
    rod0=get_origin(P["rod"]); cyl0=get_origin(P["cylinder"])
    moved=(cyl0[0]-10.0,cyl0[1],cyl0[2])
    set_origin(P["cylinder"],moved)
    require(asm.RebuildDocument(),"Rebuild after cylinder downward stroke")
    rod1=get_origin(P["rod"]); cyl1=get_origin(P["cylinder"])
    require(max(abs(a-b) for a,b in zip(rod0,rod1))<1e-6,
            f"Rod moved during cylinder-stroke test: {rod0}->{rod1}")
    require(abs(cyl1[0]-(cyl0[0]-10.0))<1e-6,
            f"Cylinder did not move down 10 mm: {cyl0}->{cyl1}")
    require(mate_count(asm)>=10,"Mates lost during allowed cylinder axial motion")

    # Restore nominal construction, save, close, reopen, rebuild.
    set_origin(P["cylinder"],cyl0)
    require(asm.RebuildDocument(),"Rebuild after cylinder restore")
    require(max(abs(a-b) for a,b in zip(get_origin(P["cylinder"]),cyl0))<1e-6,
            "Cylinder nominal position did not restore")
    require(asm.Save(),"Save nominal assembly")
    try:asm.close()
    except Exception:pass

    final=open_model(kompas,ASSEMBLY)
    gf=group(final)
    require(set(gf)==expected,"Final reopen component set mismatch")
    require(mate_count(final)>=10,"Final reopen lost mate constraints")
    final_cyl=get_origin(gf[FILES["cylinder"]][0])
    final_rod=get_origin(gf[FILES["rod"]][0])
    require(max(abs(a-b) for a,b in zip(final_cyl,cyl0))<1e-6,"Final cylinder position drift")
    require(max(abs(a-b) for a,b in zip(final_rod,rod0))<1e-6,"Final rod position drift")
    try:final.close()
    except Exception:pass

    native_file(ASSEMBLY)
    lines=[
      "SOURCE_FIGURE_59R_COMPONENT_CONTRACT_PASS",
      "ALL_REQUIRED_M3D_REOPEN_REBUILD_PASS",
      "A3D_RELATIVE_DEPENDENCIES_PASS",
      "POSITIONS_1_TO_10_PRESENT_PASS",
      f"MATE_CONSTRAINT_COUNT={mate_count(open_model(kompas,ASSEMBLY))}",
      "REAL_3D_MATES_REOPEN_PASS",
      "CENTRAL_AXIS_CHAIN_PASS",
      "CLAMP_SUPPORT_WORKPIECE_GEOMETRY_PASS",
      f"CYLINDER_NOMINAL_X={cyl0[0]:.6f}",
      f"CYLINDER_TEST_X={cyl1[0]:.6f}",
      f"ROD_X_BEFORE={rod0[0]:.6f}",
      f"ROD_X_AFTER={rod1[0]:.6f}",
      "CYLINDER_BODY_DOWNWARD_MOTION_PASS",
      "ROD_PISTON_STATIONARY_REACTION_PASS",
      "CYLINDER_NOMINAL_RESTORE_PASS",
      "FINAL_SAVE_CLOSE_REOPEN_REBUILD_PASS",
    ]
    for p in all_parts+[ASSEMBLY]:
        lines.append(f"SHA256 {p.name} {sha256(p)}")
    lines.append("RESULT=PASS_NATIVE_WORK5_VARIANT16_ORGSTANKINPROM")
    REPORT.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"),end="")

if __name__=="__main__":
    try:main()
    except Exception as exc:
        OUT.mkdir(parents=True,exist_ok=True)
        REPORT.write_text("RESULT=FAIL_NATIVE_WORK5_VARIANT16\n"+repr(exc)+"\n",encoding="utf-8")
        print(REPORT.read_text(encoding="utf-8"),file=sys.stderr)
        raise
