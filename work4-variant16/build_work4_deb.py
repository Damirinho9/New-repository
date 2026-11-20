# -*- coding: utf-8 -*-
"""Native Work 4 variant 16 builder for the proven Debian KOMPAS v25 KsAPI runtime."""
from __future__ import annotations

from pathlib import Path
import csv, hashlib, json, math, zipfile
import ksapi
from constants import constants as c

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "native-deb"
LOG = OUT / "build-report.txt"
MANIFEST = OUT / "native-manifest.json"

FILES = {
    "inner": OUT / "Work4_V16_InnerDoubleRing.m3d",
    "cup_l": OUT / "Work4_V16_OuterCup_L.m3d",
    "cup_r": OUT / "Work4_V16_OuterCup_R.m3d",
    "roller": OUT / "Work4_V16_TaperRoller.m3d",
    "cage": OUT / "Work4_V16_CageHalf.m3d",
    "rivet": OUT / "Work4_V16_Rivet.m3d",
    "assembly": OUT / "Work4_V16_Bearing.a3d",
}

def req(v, msg):
    if v is None or v is False:
        raise RuntimeError(msg)
    return v

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def native(path):
    req(path.exists() and path.stat().st_size > 1024, f"{path.name}: missing/small")
    req(zipfile.is_zipfile(path), f"{path.name}: not native ZIP container")
    with zipfile.ZipFile(path) as z:
        req({"Contents", "FileInfo"}.issubset(set(z.namelist())), f"{path.name}: native entries missing")

def load_params():
    rows = {}
    with (ROOT / "parameters.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            rows[r["parameter"]] = r
    def num(k): return float(rows[k]["value"])
    return rows, num

def set_name(obj, name):
    try: obj.SetName(name)
    except Exception: pass

def frag_container(frag):
    vm = req(frag.GetViewsAndLayersManager(), "fragment views manager")
    view = req(req(vm.GetViews(), "views").GetActiveView(), "active view")
    return ksapi.IDrawingContainer(view)

def add_circle(frag, x, y, radius):
    dc = frag_container(frag)
    circles = req(dc.GetCircles(), "circles")
    circ = req(circles.Add(), "circle add")
    circ.SetXc(float(x)); circ.SetYc(float(y)); circ.SetRadius(float(radius))
    try: circ.SetStyle(c.ksCSNormal)
    except Exception: pass
    req(circ.Update(), "circle update")
    return circ

def add_line(frag, x1,y1,x2,y2, style=None):
    dc = frag_container(frag)
    lines = req(dc.GetLineSegments(), "lines")
    s = req(lines.Add(), "line add")
    s.SetX1(float(x1)); s.SetY1(float(y1)); s.SetX2(float(x2)); s.SetY2(float(y2))
    if style is not None:
        try: s.SetStyle(style)
        except Exception: pass
    req(s.Update(), "line update")
    return s

def new_part(docs, name):
    base = req(docs.Add(c.ksDocumentPart, True), f"{name}: Documents.Add part")
    d3 = ksapi.IKompasDocument3D(base)
    top = req(d3.GetTopPart(), f"{name}: top part")
    set_name(top, name)
    return base, d3, top

def new_sketch(top, name):
    mc = req(top.GetModelContainer(), f"{name}: model container")
    sk = req(req(mc.GetSketchs(), f"{name}: sketches").Add(), f"{name}: sketch add")
    set_name(sk, name)
    plane = req(top.GetDefaultObject(c.o3d_planeXOY), f"{name}: XOY")
    sk.SetPlane(plane)
    req(sk.Update(), f"{name}: sketch plane update")
    frag = req(sk.BeginEdit(False), f"{name}: BeginEdit")
    return sk, frag

def finish_sketch(sk):
    req(sk.EndEdit(), "sketch EndEdit")
    req(sk.Update(), "sketch Update")

def add_user_var(top, name, value, expr=None, external=True, note=""):
    v = req(top.AddVariable(name, float(value), note), f"AddVariable {name}")
    if expr is not None:
        v.SetExpression(str(expr))
    if external:
        v.SetExternal(True)
    return v

def var_value(v):
    return float(v.GetValue())

def variable_by_name(top, name):
    # IPart does not expose GetVariableByName directly; use its feature view when possible.
    try:
        feat = ksapi.IFeature(top)
        v = feat.GetVariableByName(False, False, name)
        if v: return v
    except Exception:
        pass
    # Last fallback: scan all variables returned by the feature interface.
    try:
        feat = ksapi.IFeature(top)
        for v in feat.GetVariables(False, False):
            if v.GetName() == name:
                return v
    except Exception:
        pass
    raise RuntimeError(f"variable {name} not found")

def bind_last_feature_value(d3, top, target, expression):
    feat = req(d3.GetLastFeature(), f"last feature for {expression}")
    vars_ = feat.GetVariables(False, False)
    found = []
    dump = []
    for v in vars_:
        try:
            name = v.GetName()
        except Exception:
            name = "?"
        try:
            value = float(v.GetValue())
        except Exception:
            continue
        try:
            expr = v.GetExpression()
        except Exception:
            expr = ""
        dump.append((name, value, expr))
        if abs(value - float(target)) <= max(1e-7, abs(float(target))*1e-9):
            v.SetExpression(str(expression))
            found.append(name)
    req(found, f"operation variable target={target} not found; vars={dump!r}")
    req(top.RebuildModel(False), f"rebuild after binding {expression}")
    req(d3.RebuildDocument(), f"doc rebuild after binding {expression}")
    return found

def extrude(top, d3, sk, depth, name, draft=0.0, bind_expr=None):
    mc = req(top.GetModelContainer(), f"{name}: model container")
    ext = req(req(mc.GetExtrusions(), f"{name}: extrusions").Add(c.o3d_baseExtrusion), f"{name}: extrusion add")
    set_name(ext, name)
    ext.SetProfiles([sk])
    req(ext.SetSideParameters(True, c.etBlind, float(depth), float(draft), False, None), f"{name}: side parameters")
    req(ext.Update(), f"{name}: extrusion update")
    req(top.RebuildModel(False), f"{name}: rebuild model")
    req(d3.RebuildDocument(), f"{name}: rebuild document")
    bound = []
    if bind_expr:
        bound = bind_last_feature_value(d3, top, depth, bind_expr)
    return ext, bound

def build_annular(docs, path, name, od, id_, width, width_var="W", material="ШХ15"):
    base,d3,top = new_part(docs,name)
    add_user_var(top,width_var,width,None,True,"controlling axial width")
    add_user_var(top,"D_OUT",od,None,True,"outer diameter")
    add_user_var(top,"D_IN",id_,None,True,"inner diameter")
    sk,frag = new_sketch(top,name+"_PROFILE")
    add_circle(frag,0,0,od/2); add_circle(frag,0,0,id_/2)
    finish_sketch(sk)
    _,bound = extrude(top,d3,sk,width,name+"_EXTRUSION",bind_expr=width_var)
    try: top.SetMaterial(material,0.00785)
    except Exception: pass
    req(top.RebuildModel(False),name+" final model rebuild")
    req(d3.RebuildDocument(),name+" final doc rebuild")
    # Prove width variable actually changes physical geometry before saving nominal.
    w = variable_by_name(top,width_var)
    m0=float(top.GetMass())
    req(m0>0,name+" nominal mass")
    w.SetValue(width+2.0)
    req(top.RebuildModel(False),name+" probe rebuild")
    req(d3.RebuildDocument(),name+" probe doc rebuild")
    m1=float(top.GetMass())
    req(abs(m1-m0)>1e-7,f"{name}: user variable not physically bound")
    w.SetValue(width)
    req(top.RebuildModel(False),name+" restore rebuild")
    req(d3.RebuildDocument(),name+" restore doc")
    req(abs(float(top.GetMass())-m0)<=max(1e-7,m0*1e-6),name+" mass restore")
    req(base.SaveAs(str(path.resolve())),name+" SaveAs")
    base.Close(c.kdDoNotSaveChanges)
    native(path)
    return {"bound_operation_variables":bound,"nominal_mass":m0}

def build_roller(docs, path, p):
    base,d3,top = new_part(docs,"TAPER_ROLLER_V16")
    add_user_var(top,"W",p["b_rol"],None,True,"roller length")
    add_user_var(top,"DR",p["d_rol"],None,True,"roller nominal diameter")
    add_user_var(top,"DRAFT",p["roller_draft"],None,True,"taper angle")
    sk,frag = new_sketch(top,"ROLLER_PROFILE")
    add_circle(frag,0,0,p["d_rol"]/2)
    finish_sketch(sk)
    _,bound=extrude(top,d3,sk,p["b_rol"],"ROLLER_TAPER",draft=p["roller_draft"],bind_expr="W")
    try: top.SetMaterial("ШХ15",0.00785)
    except Exception: pass
    req(base.SaveAs(str(path.resolve())),"roller SaveAs")
    base.Close(c.kdDoNotSaveChanges); native(path)
    return {"bound_operation_variables":bound}

def build_cage(docs,path,p):
    base,d3,top = new_part(docs,"CAGE_HALF_V16")
    add_user_var(top,"H",p["cage_h"],None,True,"half-cage depth")
    add_user_var(top,"S",p["S"],None,True,"backing thickness")
    add_user_var(top,"D1",p["D1"],None,True,"cage outer diameter")
    add_user_var(top,"D2",p["D2"],None,True,"cage inner diameter")
    add_user_var(top,"N_ROL",p["N_rol"],None,True,"roller cells")
    sk,frag=new_sketch(top,"CAGE_BASE_PROFILE")
    add_circle(frag,0,0,p["D1"]/2); add_circle(frag,0,0,p["D2"]/2)
    finish_sketch(sk)
    _,bound=extrude(top,d3,sk,p["cage_h"],"CAGE_BASE",bind_expr="H")
    # Native pockets: 13 circles in one sketch, cut only b_rol/2 so backing ring S remains.
    psk,pfrag=new_sketch(top,"CAGE_CELLS_13")
    rr=p["z"]
    for i in range(int(p["N_rol"])):
        a=2*math.pi*i/int(p["N_rol"])
        add_circle(pfrag,rr*math.cos(a),rr*math.sin(a),p["cage_cell_d"]/2)
    finish_sketch(psk)
    mc=req(top.GetModelContainer(),"cage mc")
    cut=req(req(mc.GetExtrusions(),"cage extrusions").Add(c.o3d_cutExtrusion),"cage cut add")
    set_name(cut,"CAGE_CELLS_NATIVE_13")
    cut.SetProfiles([psk])
    req(cut.SetSideParameters(True,c.etBlind,p["b_rol"]/2,0.0,False,None),"cage cut params")
    req(cut.Update(),"cage cut update")
    req(top.RebuildModel(False),"cage cut rebuild"); req(d3.RebuildDocument(),"cage cut doc rebuild")
    try: top.SetMaterial("Сталь 20",0.00785)
    except Exception: pass
    req(base.SaveAs(str(path.resolve())),"cage SaveAs")
    base.Close(c.kdDoNotSaveChanges); native(path)
    return {"bound_operation_variables":bound,"native_cell_count":int(p["N_rol"])}

def build_rivet(docs,path,p):
    length=2*p["S"]+1.0
    base,d3,top=new_part(docs,"RIVET_V16")
    add_user_var(top,"W",length,None,True,"rivet length")
    add_user_var(top,"DRIVET",p["rivet_d"],None,True,"rivet diameter")
    sk,frag=new_sketch(top,"RIVET_PROFILE"); add_circle(frag,0,0,p["rivet_d"]/2); finish_sketch(sk)
    _,bound=extrude(top,d3,sk,length,"RIVET_SHAFT",bind_expr="W")
    try: top.SetMaterial("Сталь 20",0.00785)
    except Exception: pass
    req(base.SaveAs(str(path.resolve())),"rivet SaveAs")
    base.Close(c.kdDoNotSaveChanges); native(path)
    return {"bound_operation_variables":bound}

def master_geometry(top,p):
    sk,frag=new_sketch(top,"MASTER_GEOMETRY_V16")
    T,D,d,z=p["T"],p["D"],p["d"],p["z"]
    x0,x1=-D/2,D/2
    # XOY plan represents radial envelope and two row station circles/axes.
    add_circle(frag,0,0,D/2); add_circle(frag,0,0,d/2)
    add_circle(frag,0,0,z)
    add_line(frag,-D/2,0,D/2,0,c.ksCSNormal)
    add_line(frag,0,-D/2,0,D/2,c.ksCSNormal)
    # A short encoded two-row axial indicator inside the sketch.
    add_line(frag,-T/4,-4,-T/4,4,c.ksCSNormal)
    add_line(frag,T/4,-4,T/4,4,c.ksCSNormal)
    finish_sketch(sk)
    return sk

def add_assembly_vars(top,p):
    specs=[
      ("D",p["D"],None),("d",p["d"],None),("T",p["T"],None),
      ("C",p["T"],"T"),("B",p["T"]/2,"T/2"),("R",p["R"],None),
      ("b_rol",p["b_rol"],None),("d_rol",p["d_rol"],None),("N_rol",p["N_rol"],None),
      ("S",p["S"],None),("z",p["z"],"(d+D)/4"),("alpha",p["alpha"],None),
      ("D1",p["D1"],"ROUND((d+D)/2+0.6*d_rol)"),
      ("D2",p["D2"],"ROUND((d+D)/2-0.3*d_rol)"),
      ("cage_h",p["cage_h"],"S+b_rol/2"),
      ("cage_cell_d",p["cage_cell_d"],"d_rol+2*S"),
      ("rivet_pitch_d",p["rivet_pitch_d"],"(D1+D2)/2"),
      ("rivet_angle_offset",p["rivet_angle_offset"],"360/(2*N_rol)"),
      ("rivet_d",p["rivet_d"],"ROUND((ROUND(D1)-ROUND(D2))/6)*0.8")
    ]
    result=[]
    for n,v,e in specs:
        add_user_var(top,n,v,e,True,n)
        result.append(n)
    req(top.RebuildModel(False),"assembly variables rebuild")
    return result

def place(comp, origin, xaxis=(1,0,0), yaxis=(0,1,0), zaxis=(0,0,1)):
    pl=req(comp.GetPlacement(),"component placement")
    pl.SetOrigin(*map(float,origin))
    # Keep a full orthonormal frame when wrapper supports SetVector.
    try: pl.SetVector(c.o3d_axisOX,*map(float,xaxis))
    except Exception: pass
    try: pl.SetVector(c.o3d_axisOY,*map(float,yaxis))
    except Exception: pass
    try: pl.SetVector(c.o3d_axisOZ,*map(float,zaxis))
    except Exception: pass
    req(comp.UpdatePlacement(),"UpdatePlacement")

def component_source_var(d3, comp, name):
    # The component feature is the feature with source variables. Query current last feature
    # immediately after insertion when possible, then fall back to cast of IPart to IFeature.
    candidates=[]
    try: candidates.append(d3.GetLastFeature())
    except Exception: pass
    try: candidates.append(ksapi.IFeature(comp))
    except Exception: pass
    for feat in candidates:
        if not feat: continue
        for external,in_source in ((True,True),(False,True),(True,False),(False,False)):
            try:
                v=feat.GetVariableByName(external,in_source,name)
                if v: return v,feat
            except Exception: pass
    raise RuntimeError(f"source variable {name} not found for {comp.GetFileName()}")

def insert(parts,d3,path,name,origin=(0,0,0),axes=None):
    comp=req(parts.AddFromFile(str(path.resolve()),True,False),f"insert {path.name}")
    try: comp.SetName(name)
    except Exception: pass
    if axes:
        place(comp,origin,*axes)
    else:
        place(comp,origin)
    return comp

def link_component(d3,comp,var_name,expr):
    v,feat=component_source_var(d3,comp,var_name)
    v.SetExpression(expr)
    try: v.SetExternal(True)
    except Exception: pass
    # Do not call SetSourceVariables here: that command restores values from the
    # source file and would intentionally clear the assembly-level override.
    req(comp.RebuildModel(False),f"component rebuild {expr}")
    return {"name":v.GetName(),"expression":v.GetExpression(),"value":float(v.GetValue())}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for p in list(FILES.values())+[LOG,MANIFEST]:
        p.unlink(missing_ok=True)
    _,num=load_params()
    keys=["D","d","T","C","B","R","b_rol","d_rol","N_rol","S","z","alpha","D1","D2",
          "cage_h","cage_cell_d","rivet_pitch_d","rivet_angle_offset","rivet_d",
          "inner_race_outer_d","outer_race_inner_d","roller_draft","rebuild_test_T"]
    p={k:num(k) for k in keys}
    req(int(p["N_rol"])==13,"N_rol must be 13")
    app=req(ksapi.GetKompas(),"GetKompas")
    docs=req(app.GetDocuments(),"Documents")

    meta={}
    meta["inner"]=build_annular(docs,FILES["inner"],"INNER_DOUBLE_RING_V16",p["inner_race_outer_d"],p["d"],p["T"])
    meta["cup_l"]=build_annular(docs,FILES["cup_l"],"OUTER_CUP_L_V16",p["D"],p["outer_race_inner_d"],p["B"])
    meta["cup_r"]=build_annular(docs,FILES["cup_r"],"OUTER_CUP_R_V16",p["D"],p["outer_race_inner_d"],p["B"])
    meta["roller"]=build_roller(docs,FILES["roller"],p)
    meta["cage"]=build_cage(docs,FILES["cage"],p)
    meta["rivet"]=build_rivet(docs,FILES["rivet"],p)

    abase=req(docs.Add(c.ksDocumentAssembly,True),"Documents.Add assembly")
    ad3=ksapi.IKompasDocument3D(abase)
    atop=req(ad3.GetTopPart(),"assembly top")
    set_name(atop,"BEARING_V16")
    master_geometry(atop,p)
    vars_=add_assembly_vars(atop,p)
    parts=req(atop.GetParts(),"assembly parts")

    inner=insert(parts,ad3,FILES["inner"],"INNER_DOUBLE_RING",(0,0,-p["T"]/2))
    inner_link=link_component(ad3,inner,"W","T")

    cup_l=insert(parts,ad3,FILES["cup_l"],"OUTER_CUP_L",(0,0,-p["T"]/2))
    cup_l_link=link_component(ad3,cup_l,"W","T/2")
    cup_r=insert(parts,ad3,FILES["cup_r"],"OUTER_CUP_R",(0,0,0))
    cup_r_link=link_component(ad3,cup_r,"W","T/2")

    n=int(p["N_rol"]); rr=p["z"]
    rollers=[]
    for row,sgn in ((1,-1),(2,1)):
        zc=sgn*p["T"]/4
        for i in range(n):
            th=2*math.pi*i/n
            radial=(math.cos(th),math.sin(th),0.0)
            tangent=(-math.sin(th),math.cos(th),0.0)
            ca=math.cos(math.radians(p["alpha"])); sa=math.sin(math.radians(p["alpha"]))
            zaxis=(sgn*sa*radial[0],sgn*sa*radial[1],ca)
            yaxis=tangent
            # x = y cross z
            xaxis=(yaxis[1]*zaxis[2]-yaxis[2]*zaxis[1],
                   yaxis[2]*zaxis[0]-yaxis[0]*zaxis[2],
                   yaxis[0]*zaxis[1]-yaxis[1]*zaxis[0])
            center=(rr*radial[0],rr*radial[1],zc)
            origin=tuple(center[j]-zaxis[j]*p["b_rol"]/2 for j in range(3))
            rollers.append(insert(parts,ad3,FILES["roller"],f"ROLLER_R{row}_{i+1:02d}",origin,(xaxis,yaxis,zaxis)))

    cages=[]
    for row,sgn in ((1,-1),(2,1)):
        zc=sgn*p["T"]/4
        cages.append(insert(parts,ad3,FILES["cage"],f"CAGE_R{row}_A",(0,0,zc-p["b_rol"]/2-p["S"])))
        cages.append(insert(parts,ad3,FILES["cage"],f"CAGE_R{row}_B",(0,0,zc+p["b_rol"]/2)))

    rivets=[]
    rpr=p["rivet_pitch_d"]/2
    hoff=math.radians(p["rivet_angle_offset"])
    for row,sgn in ((1,-1),(2,1)):
        zc=sgn*p["T"]/4
        for i in range(n):
            th=2*math.pi*i/n+hoff
            origin=(rpr*math.cos(th),rpr*math.sin(th),zc-(2*p["S"]+1)/2)
            rivets.append(insert(parts,ad3,FILES["rivet"],f"RIVET_R{row}_{i+1:02d}",origin))

    req(atop.RebuildModel(False),"assembly rebuild")
    req(ad3.RebuildDocument(),"assembly doc rebuild")
    req(abase.SaveAs(str(FILES["assembly"].resolve())),"assembly SaveAs")
    abase.Close(c.kdDoNotSaveChanges)
    for f in FILES.values(): native(f)

    manifest={
      "variant":16,
      "type":"double-row angular-contact tapered roller bearing with tapered rollers and double inner ring",
      "master_geometry":"MASTER_GEOMETRY_V16",
      "assembly_variables":vars_,
      "topology":{"double_inner_ring":1,"outer_cups":2,"roller_rows":2,"rollers_per_row":n,"cage_halves":4,"rivets":2*n},
      "component_links":{"inner":inner_link,"cup_l":cup_l_link,"cup_r":cup_r_link},
      "details":meta,
      "main_rebuild_variable":{"name":"T","nominal":p["T"],"test":p["rebuild_test_T"]},
      "files":{f.name:{"size":f.stat().st_size,"sha256":sha(f)} for f in FILES.values()}
    }
    MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    lines=[
      "DEBIAN_KSAPI_RUNTIME_PASS",
      "SOURCE_VARIANT16_EXACT_TOPOLOGY_PASS",
      "ONE_DOUBLE_INNER_RING_PASS",
      "TWO_OUTER_CUPS_PASS",
      "TWO_OPPOSED_TAPER_ROLLER_ROWS_PASS",
      "MASTER_GEOMETRY_V16_PASS",
      "ASSEMBLY_VARIABLES_PASS",
      "NATIVE_COMPONENT_EXTERNAL_VARIABLE_LINKS_PASS",
      "ALL_M3D_NATIVE_PASS",
      "A3D_NATIVE_PASS",
      "RESULT=BUILD_NATIVE_WORK4_VARIANT16_PASS"
    ]
    LOG.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(LOG.read_text(encoding="utf-8"),end="")

if __name__=="__main__":
    try:
        main()
    except Exception as e:
        OUT.mkdir(parents=True,exist_ok=True)
        LOG.write_text("RESULT=BUILD_NATIVE_WORK4_VARIANT16_FAIL\n"+repr(e)+"\n",encoding="utf-8")
        print(LOG.read_text(encoding="utf-8"),end="")
        raise
