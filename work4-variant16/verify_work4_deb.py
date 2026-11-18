# -*- coding: utf-8 -*-
"""Strict Work 4 variant 16 native reopen/rebuild acceptance in Debian KsAPI."""
from __future__ import annotations
from pathlib import Path
import hashlib, json, math, zipfile
import ksapi
from constants import constants as c

ROOT=Path(__file__).resolve().parent
OUT=ROOT/"native-deb"
REPORT=OUT/"verification.txt"
MANIFEST=OUT/"native-manifest.json"
FILES={
 "inner":OUT/"Work4_V16_InnerDoubleRing.m3d",
 "cup_l":OUT/"Work4_V16_OuterCup_L.m3d",
 "cup_r":OUT/"Work4_V16_OuterCup_R.m3d",
 "roller":OUT/"Work4_V16_TaperRoller.m3d",
 "cage":OUT/"Work4_V16_CageHalf.m3d",
 "rivet":OUT/"Work4_V16_Rivet.m3d",
 "assembly":OUT/"Work4_V16_Bearing.a3d",
}

def req(v,msg):
    if v is None or v is False: raise RuntimeError(msg)
    return v

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def native(p):
    req(p.exists() and p.stat().st_size>1024,f"{p.name}: missing/small")
    req(zipfile.is_zipfile(p),f"{p.name}: not native")
    with zipfile.ZipFile(p) as z: req({"Contents","FileInfo"}.issubset(set(z.namelist())),f"{p.name}: entries")

def feat_var(obj,name,source=False):
    feat=ksapi.IFeature(obj)
    for ext,src in ((False,source),(True,source),(False,False),(True,True)):
        try:
            v=feat.GetVariableByName(ext,src,name)
            if v: return v
        except Exception: pass
    for ext,src in ((False,False),(True,True),(False,True),(True,False)):
        try:
            for v in feat.GetVariables(ext,src):
                if v.GetName()==name: return v
        except Exception: pass
    raise RuntimeError(f"variable {name} not found")

def parts_list(top):
    parts=req(top.GetParts(),"parts")
    out=[]
    for i in range(int(parts.GetCount())):
        p=parts.GetPart(i)
        if p: out.append(p)
    return out

def group(top):
    g={}
    for p in parts_list(top):
        n=Path(p.GetFileName()).name
        g.setdefault(n,[]).append(p)
    return g

def comp_var(comp,name):
    return feat_var(comp,name,True)

def state(d3,top,n):
    g=group(top)
    names={k:FILES[k].name for k in ("inner","cup_l","cup_r","roller","cage","rivet")}
    req(len(g.get(names["inner"],[]))==1,"one double inner ring")
    req(len(g.get(names["cup_l"],[]))==1,"left cup")
    req(len(g.get(names["cup_r"],[]))==1,"right cup")
    req(len(g.get(names["roller"],[]))==2*n,"two roller rows")
    req(len(g.get(names["cage"],[]))==4,"four cage halves")
    req(len(g.get(names["rivet"],[]))==2*n,"rivet count")
    T=feat_var(top,"T")
    B=feat_var(top,"B")
    C=feat_var(top,"C")
    inner=g[names["inner"]][0]; cl=g[names["cup_l"]][0]; cr=g[names["cup_r"]][0]
    vals={
      "T":float(T.GetValue()),"B":float(B.GetValue()),"C":float(C.GetValue()),
      "inner_mass":float(inner.GetMass()),"cup_l_mass":float(cl.GetMass()),"cup_r_mass":float(cr.GetMass()),
      "inner_W":float(comp_var(inner,"W").GetValue()),
      "cup_l_W":float(comp_var(cl,"W").GetValue()),
      "cup_r_W":float(comp_var(cr,"W").GetValue())
    }
    req(all(math.isfinite(x) for x in vals.values()),"nonfinite state")
    req(vals["inner_mass"]>0 and vals["cup_l_mass"]>0 and vals["cup_r_mass"]>0,"zero ring mass")
    return vals,g

def near(a,b,rel=1e-6): return abs(a-b)<=max(1e-7,rel*max(abs(a),abs(b),1.0))

def main():
    for p in FILES.values(): native(p)
    manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    req(manifest["variant"]==16,"manifest variant")
    req(manifest["topology"]=={"double_inner_ring":1,"outer_cups":2,"roller_rows":2,"rollers_per_row":13,"cage_halves":4,"rivets":26},"manifest topology")
    source_hash={k:sha(FILES[k]) for k in ("inner","cup_l","cup_r","roller","cage","rivet")}

    app=req(ksapi.GetKompas(),"GetKompas")
    docs=req(app.GetDocuments(),"Documents")

    detail_reopen=[]
    for k in ("inner","cup_l","cup_r","roller","cage","rivet"):
        base=req(docs.Open(str(FILES[k].resolve()),True,False),f"open {k}")
        d3=ksapi.IKompasDocument3D(base); top=req(d3.GetTopPart(),f"{k} top")
        req(d3.RebuildDocument(),f"{k} rebuild doc"); req(top.RebuildModel(False),f"{k} rebuild model")
        req(d3.GetLastFeature(),f"{k} persisted feature")
        detail_reopen.append((k,float(top.GetMass())))
        base.Close(c.kdDoNotSaveChanges)

    abase=req(docs.Open(str(FILES["assembly"].resolve()),True,False),"open assembly")
    ad3=ksapi.IKompasDocument3D(abase); atop=req(ad3.GetTopPart(),"assembly top")
    req(ad3.RebuildDocument(),"nominal assembly rebuild"); req(atop.RebuildModel(False),"nominal top rebuild")
    # Master geometry must survive by name.
    msk=req(req(atop.GetModelContainer(),"assembly model container").GetSketchs().GetSketchByName("MASTER_GEOMETRY_V16"),"master geometry")
    s0,g0=state(ad3,atop,13)
    req(near(s0["T"],40),"T nominal")
    req(near(s0["B"],20) and near(s0["C"],40),"dependent vars nominal")
    req(near(s0["inner_W"],40),"inner W nominal")
    req(near(s0["cup_l_W"],20) and near(s0["cup_r_W"],20),"cup W nominal")

    T=feat_var(atop,"T")
    T.SetValue(44.0)
    req(atop.RebuildModel(False),"T=44 top rebuild"); req(ad3.RebuildDocument(),"T=44 doc rebuild")
    s1,g1=state(ad3,atop,13)
    req(near(s1["T"],44),"T changed")
    req(near(s1["B"],22) and near(s1["C"],44),"dependent vars changed")
    req(near(s1["inner_W"],44),"inner W changed")
    req(near(s1["cup_l_W"],22) and near(s1["cup_r_W"],22),"cup W changed")
    deltas={k:abs(s1[k]-s0[k]) for k in ("inner_mass","cup_l_mass","cup_r_mass")}
    req(all(v>1e-7 for v in deltas.values()),f"physical masses did not change {deltas}")
    req(abase.Save(),"save changed assembly")
    abase.Close(c.kdDoNotSaveChanges)

    cbase=req(docs.Open(str(FILES["assembly"].resolve()),True,False),"reopen changed assembly")
    cd3=ksapi.IKompasDocument3D(cbase); ctop=req(cd3.GetTopPart(),"changed top")
    req(cd3.RebuildDocument(),"changed reopen doc rebuild"); req(ctop.RebuildModel(False),"changed reopen top rebuild")
    sc,gc=state(cd3,ctop,13)
    req(near(sc["T"],44) and near(sc["inner_W"],44) and near(sc["cup_l_W"],22),"changed state persist")
    req(not near(sc["inner_mass"],s0["inner_mass"],rel=1e-8),"changed mass persist")

    feat_var(ctop,"T").SetValue(40.0)
    req(ctop.RebuildModel(False),"restore top rebuild"); req(cd3.RebuildDocument(),"restore doc rebuild")
    sr,gr=state(cd3,ctop,13)
    req(near(sr["T"],40) and near(sr["B"],20) and near(sr["C"],40),"restore variables")
    req(near(sr["inner_W"],40) and near(sr["cup_l_W"],20) and near(sr["cup_r_W"],20),"restore external vars")
    req(near(sr["inner_mass"],s0["inner_mass"]) and near(sr["cup_l_mass"],s0["cup_l_mass"]) and near(sr["cup_r_mass"],s0["cup_r_mass"]),"restore masses")
    req(cbase.Save(),"save restored assembly")
    cbase.Close(c.kdDoNotSaveChanges)

    fbase=req(docs.Open(str(FILES["assembly"].resolve()),True,False),"final reopen")
    fd3=ksapi.IKompasDocument3D(fbase); ftop=req(fd3.GetTopPart(),"final top")
    req(fd3.RebuildDocument(),"final doc rebuild"); req(ftop.RebuildModel(False),"final top rebuild")
    sf,gf=state(fd3,ftop,13)
    req(near(sf["T"],40) and near(sf["inner_mass"],s0["inner_mass"]),"final nominal state")
    fbase.Close(c.kdDoNotSaveChanges)

    final_source={k:sha(FILES[k]) for k in source_hash}
    req(final_source==source_hash,"source M3D hashes changed by assembly overrides")

    lines=[
      "ALL_DETAILS_REOPEN_REBUILD_PASS",
      f"DETAIL_MASSES={detail_reopen!r}",
      "ASSEMBLY_REOPEN_REBUILD_PASS",
      "MASTER_GEOMETRY_REOPEN_PASS",
      "VARIANT16_COMPONENT_COUNTS_PASS",
      "MAIN_VARIABLE_T_40_PASS",
      "DEPENDENT_B_C_NOMINAL_PASS",
      "COMPONENT_EXTERNAL_W_NOMINAL_PASS",
      "MAIN_VARIABLE_T_44_PASS",
      "DEPENDENT_B_C_44_PASS",
      "COMPONENT_EXTERNAL_W_44_PASS",
      f"PHYSICAL_MASS_DELTAS={deltas!r}",
      "PHYSICAL_GEOMETRY_CHANGE_PASS",
      "CHANGED_SAVE_CLOSE_REOPEN_PASS",
      "MAIN_VARIABLE_T_RESTORE_40_PASS",
      "PHYSICAL_GEOMETRY_RESTORE_PASS",
      "SOURCE_M3D_SHA_UNCHANGED_PASS",
      "FINAL_NOMINAL_REOPEN_PASS"
    ]
    for p in FILES.values(): lines.append(f"SHA256 {p.name} {sha(p)}")
    lines.append("RESULT=PASS_NATIVE_WORK4_VARIANT16_REOPEN_REBUILD_PARAMETRIC")
    REPORT.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"),end="")

if __name__=="__main__":
    try: main()
    except Exception as e:
        OUT.mkdir(parents=True,exist_ok=True)
        REPORT.write_text("RESULT=FAIL_NATIVE_WORK4_VARIANT16\n"+repr(e)+"\n",encoding="utf-8")
        print(REPORT.read_text(encoding="utf-8"),end="")
        raise
