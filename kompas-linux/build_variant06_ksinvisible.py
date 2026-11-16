#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, math, sys, time, shutil
from pathlib import Path

BIN = Path("/opt/ascon/kompas3d-v25/Bin")
sys.path.insert(0, str(BIN))

import ksapi
from constants import constants as c

OUT = Path("/tmp/01_Mekhanizm_Variant_06_PARAMETRIC.frw")
REPORT = Path("/tmp/variant06_verification.json")

L1 = 20.0
L = 25.0
L2 = 2.0 * L
L3 = 60.0
DX = 20.0
N_RPM = 250.0
FI0 = 30.0
TOL = 0.75

def req(x, msg):
    if not x:
        raise RuntimeError(msg)
    return x

def ev(stage, **kw):
    row = {"stage": stage, **kw}
    print(json.dumps(row, ensure_ascii=False), flush=True)
    return row

def state(phi_deg):
    p = math.radians(phi_deg)
    A = (0.0, 0.0)
    C = (0.0, -L)
    B = (L1 * math.cos(p), L1 * math.sin(p))
    vx, vy = B[0] - C[0], B[1] - C[1]
    d = math.hypot(vx, vy)
    ux, uy = vx / d, vy / d
    D = (C[0] + L2 * ux, C[1] + L2 * uy)
    q = L3 * L3 - D[1] * D[1]
    if q < -1e-9:
        raise RuntimeError(f"Configuration impossible at phi={phi_deg}: q={q}")
    E = (D[0] + math.sqrt(max(0.0, q)), 0.0)
    X = (D[0] + (DX / L3) * (E[0] - D[0]),
         D[1] + (DX / L3) * (E[1] - D[1]))
    return A, B, C, D, E, X

def layer(view, number, name):
    layers = req(view.GetLayers(), "GetLayers")
    x = layers.GetLayerByNumber(number)
    if not x:
        x = req(layers.Add(), f"Add layer {number}")
        x.SetLayerNumber(number)
    x.SetName(name)
    x.SetVisible(True)
    x.SetBackground(False)
    x.SetPrintable(True)
    req(x.Update(), f"Update layer {number}")
    x.SetCurrent()
    return x

def line(drawing, a, b, layer_no=1, style=None):
    s = req(drawing.GetLineSegments().Add(), "LineSegments.Add")
    s.SetX1(float(a[0])); s.SetY1(float(a[1]))
    s.SetX2(float(b[0])); s.SetY2(float(b[1]))
    if layer_no is not None:
        s.SetLayerNumber(layer_no)
    s.SetStyle(c.ksCSNormal if style is None else style)
    req(s.Update(), "Line Update")
    return s

def constraint(obj, kind, *, partners=(), index=None, partner_index=None,
               name=None, value=None, expression=None):
    item = req(obj.NewConstraint(), f"NewConstraint type={kind}")
    item.SetConstraintType(kind)
    if index is not None:
        item.SetIndex(index)
    if partner_index is not None:
        item.SetPartnerIndex(partner_index)
    if partners:
        item.SetPartners(list(partners))
    if name is not None:
        item.SetVariable(name)
    if value is not None:
        item.SetConstraintValue(float(value))
    if expression is not None:
        item.SetExpression(str(expression))
    ok = item.Create()
    ev("constraint", type=int(kind), variable=name, created=bool(ok))
    req(ok and item.IsValid(), f"Constraint failed type={kind} variable={name}")
    return item

def drive(dim, name, value, expression=None):
    constraint(dim, c.ksCFixedDim)
    constraint(dim, c.ksCDimWithVariable, name=name, value=value, expression=expression)
    return dim

def linear_dim(symbols, seg, name, value, offset, layer_no=2, expression=None):
    x1,y1,x2,y2 = seg.GetX1(),seg.GetY1(),seg.GetX2(),seg.GetY2()
    dx,dy=x2-x1,y2-y1
    le=math.hypot(dx,dy)
    nx,ny=-dy/le,dx/le
    dim=req(symbols.GetLineDimensions().Add(), f"LineDimension {name}")
    dim.SetX1(x1); dim.SetY1(y1); dim.SetX2(x2); dim.SetY2(y2)
    dim.SetX3((x1+x2)/2+nx*offset); dim.SetY3((y1+y2)/2+ny*offset)
    dim.SetOrientation(c.ksLinDParallel)
    dim.SetLayerNumber(layer_no)
    req(dim.Update(), f"LineDimension Update {name}")
    req(dim.Associate(), f"LineDimension Associate {name}")
    drive(dim,name,value,expression)
    var=req(symbols.GetView().GetDimensionVariable(dim) if hasattr(symbols,"GetView") else None, "dummy") if False else None
    return dim

def angular_dim(symbols, baseline, crank, value, name="fi", layer_no=2):
    dim=req(symbols.GetAngleDimensions().Add(c.ksDrADimension), "AngleDimension")
    dim.SetBaseObject1(baseline); dim.SetBaseObject2(crank)
    dim.SetXc(0.0); dim.SetYc(0.0); dim.SetRadius(16.0)
    dim.SetAngle1(0.0); dim.SetAngle2(value)
    dim.SetDimensionType(c.ksADMinAngle)
    dim.SetX1(20.0); dim.SetY1(0.0)
    bx,by=crank.GetX2(),crank.GetY2()
    dim.SetX2(bx); dim.SetY2(by)
    mid=math.radians(value/2)
    dim.SetX3(18*math.cos(mid)); dim.SetY3(18*math.sin(mid))
    dim.SetLayerNumber(layer_no)
    req(dim.Update(), "AngleDimension Update")
    drive(dim,name,value)
    return dim

def read_var(doc2d, view, dim, name):
    v = None
    try:
        v = view.GetDimensionVariable(dim)
    except Exception:
        pass
    if not v:
        try:
            v = doc2d.GetVariableByName(False, name)
        except Exception:
            pass
    return req(v, f"Variable {name}")

def set_var_and_rebuild(doc2d, view, dim, name, value):
    v=read_var(doc2d,view,dim,name)
    try:
        v.SetExpression(format(value,'.12g'))
    except Exception:
        pass
    v.SetValue(float(value))
    req(doc2d.CompleteRebuildDocument(), f"Rebuild {name}={value}")
    return v

def main():
    OUT.unlink(missing_ok=True)
    REPORT.unlink(missing_ok=True)

    app=req(ksapi.GetKompas(), "GetKompas returned None")
    ev("app", name=app.GetApplicationName(True), build=app.GetBuildNumber())
    app.SetHideMessage(c.ksHideMessageYes)

    docs=req(app.GetDocuments(), "Documents")
    doc=None
    attempts=[]
    for attempt in range(20):
        for method, visible in (
            ("AddWithDefaultSettings", False),
            ("Add", False),
            ("AddWithDefaultSettings", True),
            ("Add", True),
        ):
            try:
                fn=getattr(docs, method)
                candidate=fn(c.ksDocumentFragment, visible)
                attempts.append({"attempt":attempt,"method":method,"visible":visible,"ok":bool(candidate)})
                if candidate:
                    doc=candidate
                    break
            except Exception as exc:
                attempts.append({"attempt":attempt,"method":method,"visible":visible,"error":type(exc).__name__})
        if doc:
            break
        time.sleep(1)
    ev("fragment-create", attempts=attempts[-12:])
    if not doc:
        stock=Path("/opt/ascon/kompas3d-v25/Utils/KLibEditor/Templates/Фрагмент.frw")
        scratch=Path("/tmp/work1_variant06_base.frw")
        req(stock.is_file(), f"Stock fragment template missing: {stock}")
        shutil.copyfile(stock, scratch)
        ev("fragment-fallback", stock=str(stock), scratch=str(scratch), bytes=scratch.stat().st_size)
        for visible in (False, True):
            try:
                candidate=docs.Open(str(scratch), visible, False)
                ev("fragment-open", visible=visible, ok=bool(candidate))
                if candidate:
                    doc=candidate
                    break
            except Exception as exc:
                ev("fragment-open", visible=visible, error=type(exc).__name__)
    doc=req(doc, "Create/open writable fragment")
    doc2d=req(ksapi.IKompasDocument2D(doc), "IKompasDocument2D")
    doc2d.SetParametricMode(True)
    req(doc2d.IsParametricMode(), "Parametric mode")
    view=req(doc2d.GetViewsAndLayersManager().GetViews().GetActiveView(), "Active view")
    drawing=req(ksapi.IDrawingContainer(view), "Drawing container")
    symbols=req(ksapi.ISymbols2DContainer(view), "Symbols container")

    # Required layer separation from the methodical instructions.
    layer(view,1,"Контуры механизма")
    layer(view,2,"Размеры")
    layer(view,3,"Вспомогательные построения")
    layer(view,4,"Исследование")

    A,B,C,D,E,X=state(FI0)
    crank=line(drawing,A,B,1)
    rocker=line(drawing,C,D,1)
    rod=line(drawing,D,E,1)
    baseAC=line(drawing,A,C,3,c.ksCSConstruction)
    href=line(drawing,A,(20.0,0.0),3,c.ksCSConstruction)
    dxline=line(drawing,D,X,3,c.ksCSConstruction)

    # Minimal native constraint network.
    constraint(crank,c.ksCFixedPoint,index=0)
    constraint(baseAC,c.ksCFixedPoint,index=0)
    constraint(href,c.ksCFixedPoint,index=0)
    constraint(href,c.ksCFixedPoint,index=1)
    constraint(baseAC,c.ksCVertical)
    constraint(rocker,c.ksCMergePoints,partners=[baseAC],index=0,partner_index=1)
    constraint(crank,c.ksCPointOnCurve,partners=[rocker],index=1)
    constraint(rod,c.ksCMergePoints,partners=[rocker],index=0,partner_index=1)
    constraint(rod,c.ksCHAlignPoints,partners=[crank],index=1,partner_index=0)
    constraint(dxline,c.ksCMergePoints,partners=[rod],index=0,partner_index=0)
    constraint(dxline,c.ksCPointOnCurve,partners=[rod],index=1)

    dims={}
    dims["l1"]=linear_dim(symbols,crank,"l1",L1,7)
    dims["l2"]=linear_dim(symbols,rocker,"l2",L2,-7,expression="2*L")
    dims["l3"]=linear_dim(symbols,rod,"l3",L3,7)
    dims["L"]=linear_dim(symbols,baseAC,"L",L,-8)
    dims["DX"]=linear_dim(symbols,dxline,"DX",DX,5)
    dims["fi"]=angular_dim(symbols,href,crank,FI0)

    req(doc2d.CompleteRebuildDocument(), "Initial complete rebuild")
    ev("core-built", variables=["l1","l2","l3","L","DX","fi"])

    # Verify actual parametric response, not just variable readback.
    positions={}
    for angle in (45.0,135.0,30.0):
        set_var_and_rebuild(doc2d,view,dims["fi"],"fi",angle)
        positions[str(int(angle))]=[crank.GetX2(),crank.GetY2()]
        ev("fi-test", angle=angle, B=positions[str(int(angle))])
    p45,p135=positions["45"],positions["135"]
    moved=math.hypot(p45[0]-p135[0],p45[1]-p135[1])
    req(moved>10.0, f"Geometry did not rebuild: movement={moved}")

    # Restore nominal and generate study graphics as non-parametric auxiliary geometry.
    set_var_and_rebuild(doc2d,view,dims["fi"],"fi",FI0)
    doc2d.SetParametricMode(False)

    # trajectory X
    prev=None
    trajectory=[]
    xs=[]
    angles=range(0,361,5)
    for deg in angles:
        _,_,_,d,e,x=state(0.001 if deg==0 else float(deg))
        trajectory.append(x); xs.append((deg,e[0]))
        if prev is not None: line(drawing,prev,x,4)
        prev=x

    # displacement graph for E
    emin=min(x for _,x in xs); emax=max(x for _,x in xs)
    gx,gy,sx,sy=110.0,-5.0,0.20,0.55
    line(drawing,(gx,gy),(gx+72,gy),4,c.ksCSConstruction)
    line(drawing,(gx,gy),(gx,gy+45),4,c.ksCSConstruction)
    prev=None
    for deg,xe in xs:
        p=(gx+deg*sx,gy+(xe-emin)*sy)
        if prev is not None: line(drawing,prev,p,4)
        prev=p

    # speed graph by centered finite difference.
    omega=2*math.pi*N_RPM/60.0
    period=60.0/N_RPM
    vgY=-70.0; st=280.0; sv=0.005
    line(drawing,(gx,vgY),(gx+period*st,vgY),4,c.ksCSConstruction)
    line(drawing,(gx,vgY-35),(gx,vgY+35),4,c.ksCSConstruction)
    vmax=0.0; prev=None
    for deg in range(5,360,5):
        e0=state(deg-5)[4][0]; e1=state(deg+5)[4][0]
        vel=(e1-e0)/(math.radians(10))*omega
        vmax=max(vmax,abs(vel))
        t=deg/360.0*period
        p=(gx+t*st,vgY+vel*sv)
        if prev is not None: line(drawing,prev,p,4)
        prev=p

    # extreme angular positions of CD
    rows=[]
    for deg in range(360):
        _,_,cc,dd,_,_=state(0.001 if deg==0 else deg)
        th=math.atan2(dd[1]-cc[1],dd[0]-cc[0])
        rows.append((th,deg,cc,dd))
    mn=min(rows,key=lambda r:r[0]); mx=max(rows,key=lambda r:r[0])
    for row in (mn,mx):
        _,_,cc,dd=row
        line(drawing,cc,dd,4,c.ksCSConstruction)

    swing_deg=math.degrees(mx[0]-mn[0])
    travel=emax-emin
    doc2d.SetParametricMode(True)
    req(doc2d.CompleteRebuildDocument(), "Final rebuild")

    req(doc.SaveAs(str(OUT)), "SaveAs FRW")
    req(OUT.is_file() and OUT.stat().st_size>1000, "FRW missing/small")
    data=OUT.read_bytes()
    req(data[:2]==b"PK", "Not modern native KOMPAS container")

    # Close and reopen with KOMPAS to verify persistence.
    req(doc.Close(c.kdDoNotSaveChanges), "Close built FRW")
    reopened=req(app.GetDocuments().Open(str(OUT),False,False), "Reopen FRW")
    r2=req(ksapi.IKompasDocument2D(reopened), "Reopened IKompasDocument2D")
    req(r2.IsParametricMode(), "Reopened document lost parametric mode")
    rv=req(r2.GetVariableByName(False,"fi"), "Reopened fi variable")
    before=rv.GetValue()
    rv.SetExpression("60")
    rv.SetValue(60.0)
    req(r2.CompleteRebuildDocument(), "Reopened rebuild fi=60")
    rv2=req(r2.GetVariableByName(False,"fi"), "Reopened fi readback")
    readback=rv2.GetValue()
    req(abs(readback-60.0)<1e-6, f"Reopened fi readback {readback}")
    rv2.SetExpression(format(FI0,'.12g')); rv2.SetValue(FI0)
    req(r2.CompleteRebuildDocument(), "Restore reopened fi")
    req(reopened.Save(), "Save restored FRW")

    result={
        "result":"PASS_NATIVE_PARAMETRIC_VARIANT06",
        "file":str(OUT),
        "size":OUT.stat().st_size,
        "sha256":hashlib.sha256(OUT.read_bytes()).hexdigest(),
        "parameters":{"l1":L1,"l2":L2,"l3":L3,"L":L,"DX":DX,"n_rpm":N_RPM},
        "fi_movement_B_45_to_135_mm":moved,
        "reopen_fi_before":before,
        "reopen_fi_test":readback,
        "slider_E_travel_mm":travel,
        "CD_swing_deg":swing_deg,
        "vmax_mm_s_approx":vmax,
    }
    REPORT.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=="__main__":
    main()
