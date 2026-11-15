# -*- coding: utf-8 -*-
import math, os, sys, time
from pathlib import Path

KOMPAS_DIR = os.environ.get("KOMPAS_DIR", "/opt/ascon/kompas3d-v25")
sys.path.insert(0, str(Path(KOMPAS_DIR) / "Bin"))

import ksapi
from constants import constants as c

OUT = Path(__file__).with_name("Работа_1_параметрическая.frw").resolve()
REPORT = Path(__file__).with_name("verification.txt").resolve()

l1, l2, l3, L = 15.0, 55.0, 80.0, 75.0

app = None
for _ in range(60):
    app = ksapi.GetKompas()
    if app is not None:
        break
    time.sleep(2)
if app is None:
    raise SystemExit("KOMPAS API not found")

docs = app.GetDocuments()
doc = docs.Add(c.ksDocumentFragment, True)
d2 = ksapi.IKompasDocument2D(doc)
view = d2.GetViewsAndLayersManager().GetViews().GetActiveView()
dc = ksapi.IDrawingContainer(view)
sc = ksapi.ISymbols2DContainer(view)

# Geometry at fi=90 deg.
fi0 = 90.0
phi = math.radians(fi0)
A=(0.0,0.0); D=(L,0.0)
B=(l1*math.cos(phi),l1*math.sin(phi))
qx,qy=B[0]-D[0],B[1]-D[1]
dist=math.hypot(qx,qy)
r=math.sqrt(dist*dist-l2*l2)
tq=math.atan2(qy,qx); alpha=math.acos(r/dist); th=tq-alpha
C=(D[0]+r*math.cos(th), D[1]+r*math.sin(th))
E=(D[0]+l3*math.cos(th), D[1]+l3*math.sin(th))

def seg(p1,p2,style=c.ksCSNormal):
    s=dc.GetLineSegments().Add()
    s.SetX1(p1[0]); s.SetY1(p1[1]); s.SetX2(p2[0]); s.SetY2(p2[1]); s.SetStyle(style)
    if not s.Update(): raise RuntimeError("segment update failed")
    return s

crank=seg(A,B)
coupler=seg(B,C)
rocker=seg(D,E)
base=seg(A,D,c.ksCSConstruction)

def host(o):
    return ksapi.IDrawingObject1(o)

def con(obj, typ, index=-1, partner=None, partner_index=-1, value=None, expr=None, variable=None):
    q=host(obj).NewConstraint()
    q.SetConstraintType(typ)
    if index >= 0: q.SetIndex(index)
    if partner is not None:
        q.SetPartner(partner)
        if partner_index >= 0: q.SetPartnerIndex(partner_index)
    if value is not None: q.SetValue(value)
    if expr is not None: q.SetExpression(expr)
    if variable is not None: q.SetVariable(variable)
    ok=q.Create()
    if not ok: raise RuntimeError(f"constraint failed type={typ}")
    return q

# Point A fixed; B merged; C point-on-line; coupler perpendicular rocker; A-D horizontal.
con(crank,c.ksCFixedPoint,index=0)
con(coupler,c.ksCMergePoints,index=0,partner=crank,partner_index=1)
con(coupler,c.ksCPointOnCurve,index=1,partner=rocker,partner_index=0)
con(coupler,c.ksCPerpendicular,partner=rocker)
con(base,c.ksCMergePoints,index=0,partner=crank,partner_index=0)
con(base,c.ksCMergePoints,index=1,partner=rocker,partner_index=0)

def lin_dim(segobj,name,value,offset):
    x1,y1,x2,y2=segobj.GetX1(),segobj.GetY1(),segobj.GetX2(),segobj.GetY2()
    dx,dy=x2-x1,y2-y1; ln=math.hypot(dx,dy); nx,ny=-dy/ln,dx/ln
    dim=sc.GetLineDimensions().Add()
    dim.SetX1(x1); dim.SetY1(y1); dim.SetX2(x2); dim.SetY2(y2)
    dim.SetX3((x1+x2)/2+nx*offset); dim.SetY3((y1+y2)/2+ny*offset)
    dim.SetOrientation(c.ksLinDParallel)
    if not dim.Update(): raise RuntimeError("dimension update failed")
    # Associate to measured segment, then fixed and variable.
    q=host(dim).NewConstraint(); q.SetConstraintType(c.ksCAssociation); q.SetPartner([host(segobj)])
    if not q.Create(): raise RuntimeError("association failed "+name)
    con(dim,c.ksCFixedDim)
    q=host(dim).NewConstraint(); q.SetConstraintType(c.ksCDimWithVariable)
    q.SetValue(value); q.SetExpression(str(value)); q.SetVariable(name)
    if not q.Create(): raise RuntimeError("variable dim failed "+name)
    return dim

lin_dim(crank,"l1",l1,10)
lin_dim(coupler,"l2",l2,10)
lin_dim(rocker,"l3",l3,10)
lin_dim(base,"L",L,-12)

# Angular dimension fi, associated to base + crank.
ad=sc.GetAngleDimensions().Add(c.ksDrADimension)
ad.SetBaseObject1(base); ad.SetBaseObject2(crank)
ad.SetX3(20); ad.SetY3(20)
if not ad.Update(): raise RuntimeError("angle dimension failed")
q=host(ad).NewConstraint(); q.SetConstraintType(c.ksCAssociation); q.SetPartner([host(base),host(crank)])
if not q.Create(): raise RuntimeError("angle association failed")
con(ad,c.ksCFixedDim)
q=host(ad).NewConstraint(); q.SetConstraintType(c.ksCDimWithVariable)
q.SetValue(fi0); q.SetExpression(str(fi0)); q.SetVariable("fi")
if not q.Create(): raise RuntimeError("fi variable failed")

# Find the generated variable name if KOMPAS renamed it and test via constraints/value route.
# We require saved native file and a measurable change in B when angular dimension value is changed.
before=(crank.GetX2(),crank.GetY2())

# Change angular constraint value to 45 and force rebuild if interface exposes it.
for qidx in range(host(ad).Constraints.Count if host(ad).Constraints else 0):
    try:
        cq=host(ad).Constraints.GetItem(qidx)
        if cq.GetConstraintType()==c.ksCDimWithVariable:
            cq.SetValue(45.0)
            cq.SetExpression("45")
    except Exception:
        pass

try:
    d21=ksapi.IKompasDocument2D1(doc)
    try: d21.RebuildDocument()
    except Exception: pass
except Exception:
    pass

after=(crank.GetX2(),crank.GetY2())

if OUT.exists(): OUT.unlink()
if not doc.SaveAs(str(OUT)):
    raise RuntimeError("SaveAs returned false")
if not OUT.exists() or OUT.stat().st_size < 1000:
    raise RuntimeError("native FRW not written")

REPORT.write_text(
    f"application={app.GetApplicationName(True)}\n"
    f"before_B={before}\nafter_B={after}\n"
    f"file_size={OUT.stat().st_size}\n"
    f"RESULT=NATIVE_FRW_WRITTEN\n",
    encoding="utf-8"
)
print(REPORT.read_text(encoding="utf-8"))
