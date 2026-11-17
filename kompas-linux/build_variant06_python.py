from __future__ import annotations
import math, pathlib, hashlib, json, sys, traceback, os, os, shutil

import ksapi
from constants import constants as c

OUT = pathlib.Path("/tmp/01_Mekhanizm_Variant_06_PARAMETRIC.frw")
LOG = pathlib.Path("/tmp/work1_v6_python.log")

L1=20.0
L=25.0
L2=50.0
L3=60.0
DX=20.0
N_RPM=250.0
FI0=90.0

def log(msg):
    print(msg, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(str(msg)+"\n")

def require(x,msg):
    if not x:
        raise RuntimeError(msg)
    return x

def state(deg):
    ph=math.radians(deg)
    A=(0.0,0.0)
    C=(0.0,-L)
    B=(L1*math.cos(ph),L1*math.sin(ph))
    vx,vy=B[0]-C[0],B[1]-C[1]
    d=math.hypot(vx,vy)
    ux,uy=vx/d,vy/d
    D=(C[0]+L2*ux,C[1]+L2*uy)
    q=L3*L3-D[1]*D[1]
    if q < 0:
        raise RuntimeError(f"invalid state fi={deg}")
    E=(D[0]+math.sqrt(q),0.0)
    X=(D[0]+(DX/L3)*(E[0]-D[0]),D[1]+(DX/L3)*(E[1]-D[1]))
    return A,B,C,D,E,X

def constraint(obj, kind, partners=(), index=None, partner_index=None, name=None, value=None, expression=None):
    item=require(obj.NewConstraint(), f"NewConstraint type={kind}")
    item.SetConstraintType(kind)
    if index is not None: item.SetIndex(index)
    if partner_index is not None: item.SetPartnerIndex(partner_index)
    if partners: item.SetPartners(list(partners))
    if name is not None: item.SetVariable(name)
    if value is not None: item.SetConstraintValue(value)
    if expression is not None: item.SetExpression(expression)
    ok=item.Create()
    log(f"constraint type={kind} name={name} ok={ok} valid={item.IsValid() if ok else None}")
    require(ok and item.IsValid(), f"Constraint failed type={kind} name={name}")
    return item

def driving(dim,name,value,expression=None):
    constraint(dim,c.ksCFixedDim)
    constraint(dim,c.ksCDimWithVariable,name=name,value=value,expression=expression)
    return dim

def make_layer(view, number, name):
    layers=require(view.GetLayers(),"GetLayers")
    layer=layers.GetLayerByNumber(number)
    if not layer:
        layer=require(layers.Add(),f"Layer Add {number}")
    layer.SetLayerNumber(number)
    layer.SetName(name)
    layer.SetBackground(False)
    layer.SetVisible(True)
    layer.SetPrintable(True)
    require(layer.Update(),f"Layer Update {number}")
    log(f"LAYER {number}={name}")
    return layer

def seg(dc,a,b,style=c.ksCSNormal,layer=0):
    s=require(dc.GetLineSegments().Add(),"Segment Add")
    s.SetX1(a[0]); s.SetY1(a[1]); s.SetX2(b[0]); s.SetY2(b[1])
    s.SetStyle(style)
    if layer:
        try: s.SetLayerNumber(layer)
        except Exception: pass
    require(s.Update(),"Segment Update")
    return s

def ldim(sc,a,b,textpt,orientation,partners,name,value,expression=None,layer=2):
    d=require(sc.GetLineDimensions().Add(),f"LineDimension Add {name}")
    d.SetX1(a[0]); d.SetY1(a[1]); d.SetX2(b[0]); d.SetY2(b[1])
    d.SetX3(textpt[0]); d.SetY3(textpt[1]); d.SetOrientation(orientation)
    if layer:
        d.SetLayerNumber(layer)
    require(d.Update(),f"LineDimension Update {name}")
    require(d.Associate(),f"Associate {name}")
    log(f"associate {name} constraints={[x.GetConstraintType() for x in d.GetConstraints()]}")
    # Verify witness associations produced by Associate.
    rows=d.GetConstraints()
    for di,(p,pi) in enumerate(partners):
        ok=any(x.IsValid() and x.GetConstraintType()==c.ksCMergePoints
               and x.GetIndex()==di and x.GetPartnerIndex()==pi
               and any(o.GetId()==p.GetId() for o in x.GetPartners())
               for x in rows)
        require(ok,f"Missing witness association {name}/{di}")
    return driving(d,name,value,expression)

def adim(sc,l1,l2,pos,name,value,layer=2):
    d=require(sc.GetAngleDimensions().Add(c.ksDrADimension),f"AngleDimension Add {name}")
    d.SetBaseObject1(l1); d.SetBaseObject2(l2)
    d.SetX3(pos[0]); d.SetY3(pos[1])
    if layer:
        d.SetLayerNumber(layer)
    require(d.Update(),f"AngleDimension Update {name}")
    return driving(d,name,value)

def dim_var(view,dim,name):
    v=require(view.GetDimensionVariable(dim),f"GetDimensionVariable {name}")
    log(f"var {name}: value={v.GetValue()} expr={v.GetExpression()} readonly={v.IsReadOnly()}")
    return v

def doc_var(doc2d,name,value,note):
    v=doc2d.GetVariableByName(False,name)
    if not v:
        v=require(doc2d.AddVariable(name,float(value),note),f"AddVariable {name}")
    # Keep the variable as a real native KOMPAS document variable.
    v.SetValue(float(value))
    log(f"doc var {name}: value={v.GetValue()} expr={v.GetExpression()} readonly={v.IsReadOnly()}")
    require(abs(float(v.GetValue())-float(value))<1e-9,f"{name} value mismatch")
    return v

def set_var(doc,var,value):
    var.SetExpression(format(value,".12g"))
    var.SetValue(float(value))
    require(doc.CompleteRebuildDocument(),"CompleteRebuildDocument")
    return var.GetValue()


def resolve_view(doc2d):
    manager=require(doc2d.GetViewsAndLayersManager(),"ViewsAndLayersManager")
    views=require(manager.GetViews(),"Views")
    view=views.GetActiveView()
    if view:
        log("VIEW_RESOLVE=active")
        return view

    count=views.GetCount()
    log(f"VIEW_COUNT={count}")
    getter=getattr(views,"GetView",None)
    if getter:
        for index in range(max(0,int(count))):
            try:
                candidate=getter(index)
            except Exception:
                candidate=None
            if candidate:
                log(f"VIEW_RESOLVE=index:{index}")
                return candidate

    by_number=getattr(views,"GetViewByNumber",None)
    if by_number:
        for number in range(max(8,int(count)+4)):
            try:
                candidate=by_number(number)
            except Exception:
                candidate=None
            if candidate:
                log(f"VIEW_RESOLVE=number:{number}")
                return candidate
    raise RuntimeError("No usable 2D view after reopen")


def segment_coords(s):
    return (float(s.GetX1()),float(s.GetY1())),(float(s.GetX2()),float(s.GetY2()))


def iter_segments(dc):
    rows=require(dc.GetLineSegments(),"LineSegments after reopen")
    count=int(rows.GetCount())
    getter=getattr(rows,"GetLineSegment",None)
    require(getter,"GetLineSegment unavailable")
    seen=set()
    result=[]
    for index in list(range(max(0,count)))+list(range(1,max(0,count)+1)):
        try:
            s=getter(index)
        except Exception:
            s=None
        if not s:
            continue
        try:
            key=("id",int(s.GetId()))
        except Exception:
            key=("coords",)+tuple(round(v,8) for p in segment_coords(s) for v in p)
        if key in seen:
            continue
        seen.add(key)
        result.append(s)
    log(f"REOPEN_LINE_SEGMENTS count={count} enumerated={len(result)}")
    return result


def find_reopened_crank(dc,expected_id):
    segments=iter_segments(dc)
    for s in segments:
        try:
            if int(s.GetId())==int(expected_id):
                log(f"REOPEN_CRANK_RESOLVE=id:{expected_id}")
                return s
        except Exception:
            pass

    target_a=(0.0,0.0)
    target_b=(0.0,L1)
    for s in segments:
        a,b=segment_coords(s)
        if ((math.dist(a,target_a)<0.5 and math.dist(b,target_b)<0.5) or
            (math.dist(b,target_a)<0.5 and math.dist(a,target_b)<0.5)):
            log(f"REOPEN_CRANK_RESOLVE=geometry id={getattr(s,'GetId',lambda:'?')()}")
            return s

    for s in segments:
        try:
            log(f"REOPEN_SEGMENT_CANDIDATE id={s.GetId()} coords={segment_coords(s)}")
        except Exception:
            log(f"REOPEN_SEGMENT_CANDIDATE coords={segment_coords(s)}")
    raise RuntimeError("Could not resolve crank after reopen")


def verify_named_variables(doc2d,label):
    expected={
        "l1":L1,
        "L":L,
        "l2":L2,
        "l3":L3,
        "fi":FI0,
        "DX":DX,
        "n":N_RPM,
    }
    result={}
    for name,value in expected.items():
        v=require(doc2d.GetVariableByName(False,name),f"{label}: missing variable {name}")
        actual=float(v.GetValue())
        require(abs(actual-value)<1e-5,f"{label}: {name}={actual}, expected {value}")
        result[name]=v
        log(f"{label}_VAR {name}={actual} expr={v.GetExpression()}")
    expr=result["l2"].GetExpression().replace(" ","")
    require(expr=="2*L",f"{label}: l2 expression is {expr!r}")
    log(f"{label}_VARIABLES_PASS l1=20 L=25 l2=50 l3=60 fi=90 DX=20 n=250 expr_l2=2*L")
    return result


def rebuild_acceptance_cycle(doc2d,fi_var,crank,label):
    pts={}
    for value in (45.0,135.0,90.0):
        read=float(set_var(doc2d,fi_var,value))
        p=(float(crank.GetX2()),float(crank.GetY2()))
        expected=(L1*math.cos(math.radians(value)),L1*math.sin(math.radians(value)))
        require(abs(read-value)<1e-5,f"{label}: fi readback {read} != {value}")
        require(math.dist(p,expected)<0.5,f"{label}: B mismatch fi={value}: {p} expected {expected}")
        pts[value]=p
        log(f"{label}_FI_{int(value)}_PASS B=({p[0]:.9f},{p[1]:.9f})")

    moved=math.dist(pts[45.0],pts[135.0])
    require(moved>5.0,f"{label}: physical movement too small: {moved}")
    require(math.dist(pts[90.0],(0.0,L1))<0.5,f"{label}: final fi=90 geometry invalid")
    log(f"{label}_PHYSICAL_MOVE_PASS distance={moved:.9f}")
    log(f"{label}_RETURN_90_PASS B=({pts[90.0][0]:.9f},{pts[90.0][1]:.9f})")
    return pts,moved


def try_fragment(docs, label, factory):
    try:
        doc=factory()
        log(f"candidate {label}: doc={doc}")
        if not doc:
            return None
        try:
            doc.SetActive()
        except Exception as e:
            log(f"candidate {label}: SetActive warning {e!r}")
        d2=ksapi.IKompasDocument2D(doc)
        view=d2.GetViewsAndLayersManager().GetViews().GetActiveView()
        dc=ksapi.IDrawingContainer(view)
        probe=dc.GetLineSegments().Add()
        if not probe:
            log(f"candidate {label}: LineSegments.Add -> None")
            try: doc.Close(c.kdDoNotSaveChanges)
            except Exception: pass
            return None
        probe.SetX1(-5.0); probe.SetY1(-5.0); probe.SetX2(-1.0); probe.SetY2(-5.0)
        probe.SetStyle(c.ksCSConstruction)
        if not probe.Update():
            log(f"candidate {label}: probe Update false")
            try: doc.Close(c.kdDoNotSaveChanges)
            except Exception: pass
            return None
        probe.Delete()
        log(f"candidate {label}: PASS editable fragment")
        return doc
    except Exception as e:
        log(f"candidate {label}: EXCEPTION {e!r}")
        return None

def acquire_fragment(docs):
    template=pathlib.Path("/opt/ascon/kompas3d-v25/Utils/KLibEditor/Templates/Фрагмент.frw")
    work=pathlib.Path("/tmp/variant06_base.frw")
    shutil.copy2(template,work)

    candidates=[
        ("Add-visible", lambda: docs.Add(c.ksDocumentFragment, True)),
        ("Add-invisible", lambda: docs.Add(c.ksDocumentFragment, False)),
        ("AddDefault-visible", lambda: docs.AddWithDefaultSettings(c.ksDocumentFragment, True)),
        ("AddDefault-invisible", lambda: docs.AddWithDefaultSettings(c.ksDocumentFragment, False)),
        ("AddFromTemplate-visible", lambda: docs.AddNewDocumentFromTemplate(str(template), True)),
        ("AddFromTemplate-invisible", lambda: docs.AddNewDocumentFromTemplate(str(template), False)),
        ("Open-visible-rw", lambda: docs.Open(str(work), True, False)),
        ("Open-invisible-rw", lambda: docs.Open(str(work), False, False)),
    ]

    try:
        p=docs.GetOpenDocumentParam()
        if p:
            p.SetVisible(True); p.SetReadOnly(False)
            candidates.append(("OpenDocument-visible-rw", lambda p=p: docs.OpenDocument(str(work),p)))
    except Exception as e:
        log(f"GetOpenDocumentParam visible warning {e!r}")
    try:
        p2=docs.GetOpenDocumentParam()
        if p2:
            p2.SetVisible(False); p2.SetReadOnly(False)
            candidates.append(("OpenDocument-invisible-rw", lambda p2=p2: docs.OpenDocument(str(work),p2)))
    except Exception as e:
        log(f"GetOpenDocumentParam invisible warning {e!r}")

    for label,factory in candidates:
        doc=try_fragment(docs,label,factory)
        if doc:
            return doc,label
    raise RuntimeError("No editable fragment acquisition route worked")

def main():
    LOG.unlink(missing_ok=True)
    OUT.unlink(missing_ok=True)
    port=os.environ.get("KOMPAS_PORT")
    app=require(ksapi.IApplication(int(port)) if port else ksapi.GetKompas(),
                f"GetKompas/KOMPAS_PORT={port}")
    log("APP="+str(app.GetApplicationName(True)))
    # Official SDK license capability query; never enable or override a license.
    manager=require(app.GetApplicationLicenseManager(),"Application license manager")
    active=manager.IsKompasModuleActive(c.ksKompasModule2D)
    log(f"LICENSE_MODULE_2D_ACTIVE={active}")
    require(active,"KOMPAS 2D editing module is not active; valid license/session required")
    docs=require(app.GetDocuments(),"Documents")
    doc,route=acquire_fragment(docs)
    log("fragment route="+route)
    try: doc.SetActive()
    except Exception: pass
    d2=require(ksapi.IKompasDocument2D(doc),"IKompasDocument2D")
    d2.SetParametricMode(True)
    require(d2.IsParametricMode(),"Parametric mode")
    view=require(d2.GetViewsAndLayersManager().GetViews().GetActiveView(),"Active view")
    make_layer(view,1,"Контуры механизма")
    make_layer(view,2,"Размеры")
    make_layer(view,3,"Вспомогательные построения")
    make_layer(view,4,"Исследование")
    dc=require(ksapi.IDrawingContainer(view),"Drawing container")
    sc=require(ksapi.ISymbols2DContainer(view),"Symbols container")
    log("fragment created")

    A,B,C,D,E,X=state(FI0)
    crank=seg(dc,A,B,layer=1)
    rocker=seg(dc,C,D,layer=1)
    rod=seg(dc,D,E,layer=1)
    baseAC=seg(dc,A,C,c.ksCSConstruction,layer=3)
    href=seg(dc,A,(20.0,0.0),c.ksCSConstruction,layer=3)
    log("geometry created")

    constraint(crank,c.ksCFixedPoint,index=0)
    constraint(baseAC,c.ksCVertical)
    constraint(href,c.ksCHorizontal)
    constraint(baseAC,c.ksCMergePoints,partners=[crank],index=0,partner_index=0)
    constraint(href,c.ksCMergePoints,partners=[crank],index=0,partner_index=0)
    constraint(baseAC,c.ksCMergePoints,partners=[rocker],index=1,partner_index=0)
    constraint(crank,c.ksCPointOnCurve,partners=[rocker],index=1,partner_index=0)
    constraint(rocker,c.ksCMergePoints,partners=[rod],index=1,partner_index=0)
    constraint(crank,c.ksCHAlignPoints,partners=[rod],index=0,partner_index=1)
    log("geometric constraints created")

    d_l1=ldim(sc,A,B,(-10,10),c.ksLinDParallel,[(crank,0),(crank,1)],"l1",L1)
    d_L=ldim(sc,A,C,(-12,-12),c.ksLinDParallel,[(baseAC,0),(baseAC,1)],"L",L)
    d_l2=ldim(sc,C,D,(-10,20),c.ksLinDParallel,[(rocker,0),(rocker,1)],"l2",L2)
    d_l3=ldim(sc,D,E,(45,25),c.ksLinDParallel,[(rod,0),(rod,1)],"l3",L3)
    d_fi=adim(sc,href,crank,(13,13),"fi",FI0)
    log("driving dimensions created")

    v_l1=dim_var(view,d_l1,"l1")
    v_L=dim_var(view,d_L,"L")
    v_l2=dim_var(view,d_l2,"l2")
    v_l3=dim_var(view,d_l3,"l3")
    v_fi=dim_var(view,d_fi,"fi")

    # Variant 6 also requires two native non-dimensional document variables.
    v_DX=doc_var(d2,"DX",DX,"Расстояние от точки D до точки X, мм")
    v_n=doc_var(d2,"n",N_RPM,"Частота вращения кривошипа, об/мин")

    # Required symbolic dependency.
    v_l2.SetExpression("2*L")
    require(d2.CompleteRebuildDocument(),"rebuild l2=2*L")
    require(abs(v_l2.GetValue()-2*v_L.GetValue())<1e-5,"l2 != 2*L")
    require(v_l2.GetExpression().replace(" ","")=="2*L","l2 expression mismatch")
    require(abs(float(v_DX.GetValue())-20.0)<1e-9,"DX != 20")
    require(abs(float(v_n.GetValue())-250.0)<1e-9,"n != 250")
    log(f"l2 expression applied: {v_l2.GetExpression()} value={v_l2.GetValue()}")
    log(
        "WORK1_NATIVE_VARIABLES_PASS "
        f"l1={v_l1.GetValue()} L={v_L.GetValue()} l2={v_l2.GetValue()} "
        f"l3={v_l3.GetValue()} fi={v_fi.GetValue()} DX={v_DX.GetValue()} n={v_n.GetValue()}"
    )

    # Strict acceptance cycle 1: mutate the same native fi variable and prove
    # that the actual native crank geometry moves, then return to fi=90.
    pre_pts,pre_moved=rebuild_acceptance_cycle(d2,v_fi,crank,"PRE_SAVE")
    log(f"PRE_SAVE_PARAMETRIC_REBUILD_PASS moved={pre_moved:.9f}")

    # Static study geometry generated from exact variant 6 kinematics.
    # Trajectory of X.
    prev=None
    for deg in range(0,361,5):
        *_,xx=state(0.001 if deg==0 else deg)
        if prev is not None: seg(dc,prev,xx,layer=4)
        prev=xx

    # Slider displacement graph x_E(fi).
    samples=[]
    emin=1e99; emax=-1e99
    for deg in range(0,361,5):
        _,_,_,_,ee,_=state(0.001 if deg==0 else deg)
        samples.append((deg,ee[0]))
        emin=min(emin,ee[0]); emax=max(emax,ee[0])
    gx,gy,sx,sy=110.0,-10.0,0.20,0.55
    seg(dc,(gx,gy),(gx+360*sx,gy),c.ksCSConstruction,layer=4)
    seg(dc,(gx,gy),(gx,gy+50),c.ksCSConstruction,layer=4)
    prev=None
    for deg,e in samples:
        p=(gx+deg*sx,gy+(e-emin)*sy)
        if prev is not None: seg(dc,prev,p,layer=4)
        prev=p

    # Velocity graph.
    omega=2*math.pi*N_RPM/60.0
    period=60.0/N_RPM
    vgY=-70.0; st=280.0; sv=0.005
    seg(dc,(gx,vgY),(gx+period*st,vgY),c.ksCSConstruction,layer=4)
    seg(dc,(gx,vgY-35),(gx,vgY+35),c.ksCSConstruction,layer=4)
    prev=None; vmax=0.0
    for deg in range(5,360,5):
        _,_,_,_,e0,_=state(deg-5)
        _,_,_,_,e1,_=state(deg+5)
        vel=(e1[0]-e0[0])/math.radians(10)*omega
        vmax=max(vmax,abs(vel))
        t=deg/360.0*period
        p=(gx+t*st,vgY+vel*sv)
        if prev is not None: seg(dc,prev,p,layer=4)
        prev=p

    # Angular swing of CD.
    th=[]
    for deg in range(360):
        _,_,cc,dd,_,_=state(0.001 if deg==0 else deg)
        th.append((deg,math.atan2(dd[1]-cc[1],dd[0]-cc[0])))
    amin=min(th,key=lambda z:z[1]); amax=max(th,key=lambda z:z[1])
    for _,a in (amin,amax):
        seg(dc,C,(C[0]+L2*math.cos(a),C[1]+L2*math.sin(a)),c.ksCSConstruction,layer=4)

    log(f"travel_E={emax-emin} mm")
    log(f"swing_CD={math.degrees(amax[1]-amin[1])} deg")
    log(f"vmax={vmax} mm/s")

    # SaveAs is NOT acceptance. It is only the boundary between the two
    # independent rebuild cycles.
    crank_id=int(crank.GetId())
    require(doc.SaveAs(str(OUT)),"SaveAs")
    require(OUT.exists() and OUT.stat().st_size>1000,"FRW output after SaveAs")
    require(OUT.read_bytes()[:2]==b"PK","not modern native FRW after SaveAs")
    log(f"SAVE_AS_BEFORE_REOPEN_PASS size={OUT.stat().st_size} crank_id={crank_id}")

    # Close the original document so all following checks use freshly loaded
    # native objects from disk, not stale in-memory wrappers.
    close_result=doc.Close(c.kdDoNotSaveChanges)
    log(f"CLOSE_AFTER_SAVE_AS_PASS result={close_result!r}")

    reopened=require(docs.Open(str(OUT),True,False),"Reopen saved FRW")
    try:
        reopened.SetActive()
    except Exception as e:
        log(f"REOPEN SetActive warning {e!r}")
    try:
        app.SetActiveDocument(reopened)
    except Exception as e:
        log(f"REOPEN SetActiveDocument warning {e!r}")

    reopened_d2=require(ksapi.IKompasDocument2D(reopened),"Reopen IKompasDocument2D")
    reopened_d2.SetParametricMode(True)
    require(reopened_d2.IsParametricMode(),"Reopen parametric mode")
    reopened_view=resolve_view(reopened_d2)
    reopened_dc=require(ksapi.IDrawingContainer(reopened_view),"Reopen drawing container")

    # Re-fetch every required variable by name from the reopened native file.
    reopened_vars=verify_named_variables(reopened_d2,"REOPEN")
    reopened_crank=find_reopened_crank(reopened_dc,crank_id)

    # Strict acceptance cycle 2 after disk reopen.
    post_pts,post_moved=rebuild_acceptance_cycle(
        reopened_d2,reopened_vars["fi"],reopened_crank,"REOPEN"
    )
    log(f"REOPEN_PARAMETRIC_REBUILD_PASS moved={post_moved:.9f}")
    log(
        "REOPEN_COORDINATE_AUDIT "
        f"B45=({post_pts[45.0][0]:.9f},{post_pts[45.0][1]:.9f}) "
        f"B135=({post_pts[135.0][0]:.9f},{post_pts[135.0][1]:.9f}) "
        f"B90=({post_pts[90.0][0]:.9f},{post_pts[90.0][1]:.9f})"
    )

    # Persist the required final fi=90 state. A false return is failure; some
    # bindings may return None on success, so absence of an exception plus the
    # existing native container is accepted here.
    save_final=getattr(reopened,"Save",None)
    if save_final:
        final_save_result=save_final()
        require(final_save_result is not False,"Final Save returned False")
        log(f"FINAL_SAVE_90_PASS result={final_save_result!r}")
    else:
        require(reopened.SaveAs(str(OUT)),"Final SaveAs")
        log("FINAL_SAVE_90_PASS via SaveAs")

    require(OUT.exists() and OUT.stat().st_size>1000,"Final FRW output")
    require(OUT.read_bytes()[:2]==b"PK","Final FRW is not native ZIP container")

    # Only now may the final PASS marker, SHA-256 and deliverable be emitted.
    final_sha=hashlib.sha256(OUT.read_bytes()).hexdigest()
    log("FINAL_STATE_90_PASS")
    log(f"SHA256={final_sha}")
    log("RESULT=PASS_NATIVE_PARAMETRIC_VARIANT06")

if __name__=="__main__":
    try:
        main()
    except Exception as e:
        log("EXCEPTION "+repr(e))
        traceback.print_exc()
        sys.exit(1)
