# Candidate Windows COM port. No native acceptance until real KOMPAS runs it.
from pathlib import Path
import math
import pythoncom
from win32com.client import Dispatch, gencache
from geometry import *
HERE=Path(__file__).resolve().parent
OUT=HERE/"01_Mekhanizm_Variant_06_PARAMETRIC.frw"
KOMPAS6_CONSTANTS = "{75C9F5D0-B5B8-4526-8681-9903C567D2ED}"
KOMPAS_API7 = "{69AC2981-37C0-4379-84FD-5DD2F3C0A520}"

def add_constraint(api7, obj, ctype, index=0, partner=None, partner_index=0,
                   variable=None, value=None, expression=None, comment=None):
    c = api7.IDrawingObject1(obj).NewConstraint()
    c.ConstraintType = ctype
    c.Index = index
    if partner is not None:
        c.Partner = partner
        c.PartnerIndex = partner_index
    if variable is not None:
        c.Variable = variable
    if value is not None:
        c.Value = value
    if expression is not None:
        c.Expression = expression
    if comment is not None:
        c.Comment = comment
    if not c.Create():
        raise RuntimeError("Не удалось создать параметрическое ограничение")
    return c


def add_line(draw, const, p1, p2, construction=False):
    seg = draw.LineSegments.Add()
    seg.Style = const.ksCSConstruction if construction else const.ksCSNormal
    seg.X1, seg.Y1 = p1
    seg.X2, seg.Y2 = p2
    if not seg.Update():
        raise RuntimeError("Не удалось создать отрезок")
    return seg


def add_layer(view, name):
    layers = view.Layers
    layers.Add()
    layer = layers.Layer[layers.Count - 1]
    layer.Name = name
    layer.Current = True
    layer.Update()
    return layer


def make_linear_dim(api7, const, symbols, seg, name, value, offset=10.0):
    x1, y1, x2, y2 = seg.X1, seg.Y1, seg.X2, seg.Y2
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length, dx / length

    dim = symbols.LineDimensions.Add()
    dim.X1, dim.Y1 = x1, y1
    dim.X2, dim.Y2 = x2, y2
    dim.X3 = (x1 + x2) / 2 + nx * offset
    dim.Y3 = (y1 + y2) / 2 + ny * offset
    dim.Angle = math.degrees(math.atan2(dy, dx))
    dim.Orientation = const.ksLinDParallel
    if not dim.Update():
        raise RuntimeError("Не удалось создать линейный размер " + name)

    add_constraint(api7, dim, const.ksCMergePoints, 0, seg, 0)
    add_constraint(api7, dim, const.ksCMergePoints, 1, seg, 1)
    add_constraint(api7, dim, const.ksCFixedDim)
    add_constraint(api7, dim, const.ksCDimWithVariable,
                   variable=name, value=value, comment="Управляющий размер " + name)
    return dim


def make_angle_dim(api7, const, symbols, base_line, crank, value):
    dim = symbols.AngleDimensions.Add(const.ksDrADimension)
    dim.BaseObject1 = base_line
    dim.BaseObject2 = crank
    dim.Radius = 22.0
    dim.Direction = False
    if not dim.Update():
        raise RuntimeError("Не удалось создать угловой размер fi")
    add_constraint(api7, dim, const.ksCFixedDim)
    add_constraint(api7, dim, const.ksCDimWithVariable,
                   variable="fi", value=value, comment="Угол поворота кривошипа")
    return dim


def read_endpoint(seg, idx):
    if idx == 0:
        return float(seg.X1), float(seg.Y1)
    return float(seg.X2), float(seg.Y2)



def check_geometry(objects,angle):
    A,B,C,D,E,X=state(angle)
    for label,seg,p,q in (("AB",objects[0],A,B),("CD",objects[1],C,D),("DE",objects[2],D,E),("DX",objects[3],D,X)):
        if math.dist(read_endpoint(seg,0),p)>.15 or math.dist(read_endpoint(seg,1),q)>.15:
            raise RuntimeError(f"{label}: native coordinates mismatch at {angle}")
def main():
    pythoncom.CoInitialize()
    const=gencache.EnsureModule(KOMPAS6_CONSTANTS,0,1,0).constants
    api7=gencache.EnsureModule(KOMPAS_API7,0,1,0)
    raw=Dispatch("KOMPAS.Application.7")
    app=api7.IApplication(raw._oleobj_.QueryInterface(api7.IApplication.CLSID,pythoncom.IID_IDispatch))
    app.Visible=True
    doc=app.Documents.Add(const.ksDocumentFragment,True)
    if not doc: raise RuntimeError("No editable fragment")
    doc.Active=True
    d2=api7.IKompasDocument2D(doc); param=api7.IKompasDocument2D1(doc)
    param.ParametricMode=True
    view=d2.ViewsAndLayersManager.Views.ActiveView
    draw=api7.IDrawingContainer(view); symbols=api7.ISymbols2DContainer(view)
    A,B,C,D,E,X=state(FI0)
    add_layer(view,"Mechanism")
    crank=add_line(draw,const,A,B); rocker=add_line(draw,const,C,D); rod=add_line(draw,const,D,E)
    marker=add_line(draw,const,D,X,True)
    add_layer(view,"Reference")
    base=add_line(draw,const,A,C,True); href=add_line(draw,const,A,(20.,0.),True)
    def con(obj,kind,i=0,p=None,j=0): return add_constraint(api7,obj,kind,i,p,j)
    con(crank,const.ksCFixedPoint)
    con(base,const.ksCVertical); con(href,const.ksCHorizontal)
    con(base,const.ksCMergePoints,0,crank,0); con(href,const.ksCMergePoints,0,crank,0)
    con(base,const.ksCMergePoints,1,rocker,0)
    con(crank,const.ksCPointOnCurve,1,rocker,0)
    con(rocker,const.ksCMergePoints,1,rod,0)
    con(crank,const.ksCHAlignPoints,0,rod,1)
    con(marker,const.ksCMergePoints,0,rod,0)
    con(marker,const.ksCPointOnCurve,1,rod,0)
    add_layer(view,"Dimensions")
    for obj,name,val,offset in ((crank,"l1",L1,8.),(base,"L",L,-10.),(rocker,"l2",L2,12.),(rod,"l3",L3,10.),(marker,"DX",DX,-8.)):
        make_linear_dim(api7,const,symbols,obj,name,val,offset)
    make_angle_dim(api7,const,symbols,href,crank,FI0)
    param.Variable["l2"].Expression="2*L"
    # Frequency is a native document variable, not a drawing label.
    param.AddVariable("n",N_RPM,"rpm")
    if not param.RebuildDocument(): raise RuntimeError("Initial rebuild failed")
    for angle in (45.,135.,90.):
        param.Variable["fi"].Value=angle
        if not param.RebuildDocument(): raise RuntimeError("Rebuild failed")
        check_geometry((crank,rocker,rod,marker),angle)
    if abs(float(param.Variable["n"].Value)-N_RPM)>1e-8: raise RuntimeError("n missing")
    if param.Variable["l2"].Expression.replace(" ","")!="2*L": raise RuntimeError("dependency missing")
    # Research graphics are static analytical curves, deliberately separate.
    add_layer(view,"Study")
    param.ParametricMode=False
    series=[]
    for fi in range(361):
        x=state(fi)[4][0]
        v=(state(fi+.001)[4][0]-state(fi-.001)[4][0])/math.radians(.002)*(2*math.pi*N_RPM/60)
        series.append((fi,state(fi)[5],x,v))
    for a,b in zip(series,series[1:]):
        for p,q in ((a[1],b[1]),((110+a[0]*.2,a[2]*.5),(110+b[0]*.2,b[2]*.5)),((110+a[0]*.2,-80+a[3]*.005),(110+b[0]*.2,-80+b[3]*.005))):
            if math.dist(p,q)>1e-8: add_line(draw,const,p,q)
    param.ParametricMode=True
    doc.SaveAs(str(OUT))
    if not OUT.is_file(): raise RuntimeError("No native output")
    print("CANDIDATE_SAVED_NOT_ACCEPTED",OUT)
if __name__=="__main__": main()
