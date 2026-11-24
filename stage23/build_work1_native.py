"""Windows COM candidate for V06. Must be run on a lawfully licensed interactive workstation.
Never treats a generated file as accepted without measured geometry and reopened variables.
"""
import argparse,hashlib,json,math,os,zipfile
from pathlib import Path
import pythoncom
from win32com.client import Dispatch,gencache
from engineering import load,state
KOMPAS6_CONSTANTS = "{75C9F5D0-B5B8-4526-8681-9903C567D2ED}"
KOMPAS_API7 = "{69AC2981-37C0-4379-84FD-5DD2F3C0A520}"
KOMPAS6_API5 = "{0422828C-F174-495E-AC5D-D31014DBBE87}"

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



def need(x,m):
    if not x:raise RuntimeError(m)
    return x

def var(d,name):
    # pywin32 dispatch variants for indexed property. No silent fallback value.
    errors=[]
    for f in (lambda:d.Variable[name],lambda:d.Variable(False,name),lambda:d.Variable[name,False],lambda:d.GetVariable(False,name)):
        try:
            v=f()
            if v:return v
        except Exception as ex:errors.append(repr(ex))
    raise RuntimeError(f"Missing native variable {name}: {errors}")

def signatures(draw):
    lines=draw.LineSegments;result=[]
    for i in range(int(lines.Count)):
        for f in (lambda:lines.LineSegment[i],lambda:lines.Item(i)):
            try:
                s=f();result.append(((float(s.X1),float(s.Y1)),(float(s.X2),float(s.Y2))));break
            except Exception:continue
    return result

def audit(p,d,draw):
    a=p["work1"];vars={k:var(d,k) for k in ("l1","L","l2","l3","DX","n","fi")}
    need(str(vars["l2"].Expression).replace(" ","")==a["l2_expression"],"l2 expression mismatch")
    for k in ("l1","l3","DX","n"):
        need(abs(float(vars[k].Value)-a[k])<1e-5,f"{k} differs from contract")
    checks=[]
    for L in (20,25,30):
        vars["L"].Value=float(L)
        for angle in (45,90,135):
            vars["fi"].Value=float(angle)
            need(d.RebuildDocument(),f"Rebuild {L}/{angle}")
            need(abs(float(vars["L"].Value)-L)<1e-5,"L mutation")
            need(abs(float(vars["fi"].Value)-angle)<1e-5,"fi mutation")
            need(abs(float(vars["l2"].Value)-2*L)<1e-5,"l2 symbolic mutation")
            A,B,C,D,E,X=state(p,angle,L)
            sig=signatures(draw)
            for name,u,v in [("AB",A,B),("AC",A,C),("CD",C,D),("DE",D,E),("DX",D,X)]:
                err=min((min(max(math.dist(u,x),math.dist(v,y)),max(math.dist(u,y),math.dist(v,x))) for x,y in sig),default=float("inf"))
                need(err<0.15,f"{name} physical coordinates L={L} fi={angle} error={err}")
                checks.append({"L":L,"fi":angle,"segment":name,"max_error_mm":err})
    vars["L"].Value=float(a["L"]);vars["fi"].Value=float(a["fi"])
    need(d.RebuildDocument(),"Restore nominal")
    need(abs(float(vars["l2"].Value)-2*a["L"])<1e-5,"Restore l2")
    return checks

def setup_doc(api7,doc):
    d2=api7.IKompasDocument2D(doc);d=api7.IKompasDocument2D1(doc);d.ParametricMode=True
    view=need(d2.ViewsAndLayersManager.Views.ActiveView,"Active view")
    return d,view,api7.IDrawingContainer(view),api7.ISymbols2DContainer(view)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--parameters",required=True);ap.add_argument("--output",required=True);ap.add_argument("--seed");args=ap.parse_args()
    if os.environ.get("KOMPAS_LICENSE_CONFIRMED")!="YES":raise RuntimeError("BLOCKED: entitlement confirmation absent")
    p=load(args.parameters);a=p["work1"];out=Path(args.output).resolve();out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():raise FileExistsError(out)
    pythoncom.CoInitialize()
    const=gencache.EnsureModule(KOMPAS6_CONSTANTS,0,1,0).constants
    api7=gencache.EnsureModule(KOMPAS_API7,0,1,0)
    raw=Dispatch("KOMPAS.Application.7")
    app=api7.IApplication(raw._oleobj_.QueryInterface(api7.IApplication.CLSID,pythoncom.IID_IDispatch))
    app.Visible=True
    if args.seed:
        # Never overwrite original seed; make a local work copy.
        import shutil
        seed=out.with_name("source_copy.frw");shutil.copy2(args.seed,seed)
        doc=need(app.Documents.Open(str(seed),True,False),"Open existing FRW copy")
        d,view,draw,symbols=setup_doc(api7,doc)
        for k in ("l1","L","l3","DX","n","fi"):var(d,k).Value=float(a[k])
        var(d,"l2").Expression=a["l2_expression"]
        need(d.RebuildDocument(),"Rebuild existing FRW")
    else:
        doc=need(app.Documents.Add(const.ksDocumentFragment,True),"Create fragment")
        d,view,draw,symbols=setup_doc(api7,doc)
        A,B,C,D,E,X=state(p,a["fi"])
        add_layer(view,"Mechanism")
        crank=add_line(draw,const,A,B);rocker=add_line(draw,const,C,D);rod=add_line(draw,const,D,E);dx=add_line(draw,const,D,X,True)
        base=add_line(draw,const,A,C,True);href=add_line(draw,const,A,(a["l1"],0),True)
        def c(obj,typ,index=0,partner=None,pi=0):return add_constraint(api7,obj,getattr(const,typ),index,partner,pi)
        c(crank,"ksCFixedPoint",0)
        c(base,"ksCVertical")
        c(base,"ksCMergePoints",0,crank,0)
        c(base,"ksCMergePoints",1,rocker,0)
        c(href,"ksCMergePoints",0,crank,0)
        c(href,"ksCFixedPoint",1)
        c(crank,"ksCPointOnCurve",1,rocker,0)
        c(rocker,"ksCMergePoints",1,rod,0)
        c(crank,"ksCHAlignPoints",0,rod,1)
        c(dx,"ksCMergePoints",0,rod,0)
        c(dx,"ksCPointOnCurve",1,rod,0)
        add_layer(view,"Dimensions")
        for seg,n,val,offset in [(crank,"l1",a["l1"],10),(base,"L",a["L"],-12),(rocker,"l2",2*a["L"],-10),(rod,"l3",a["l3"],10),(dx,"DX",a["DX"],-6)]:
            make_linear_dim(api7,const,symbols,seg,n,val,offset)
        make_angle_dim(api7,const,symbols,href,crank,a["fi"])
        # API7 user functional variable; strict readback checks actual name and value.
        need(d.AddUserFuncVariable("n",str(a["n"])),"Create native n")
        var(d,"l2").Expression=a["l2_expression"]
        need(d.RebuildDocument(),"Rebuild initial constraints")
        add_layer(view,"Study nominal trajectory");d.ParametricMode=False
        pts=[state(p,i)[-1] for i in range(361)]
        for u,v in zip(pts,pts[1:]):add_line(draw,const,u,v,True)
        add_layer(view,"Study nominal displacement and velocity")
        rows=[]
        omega=2*math.pi*a["n"]/60
        for i in range(361):
            h=.001; A1,B1,C1,D1,E1,X1=state(p,i)
            ep=state(p,i+h)[4][0];em=state(p,i-h)[4][0]
            rows.append((i,math.dist(B1,C1),E1[0],(ep-em)/math.radians(2*h)*omega))
        for col,y0,ys in [(1,-10,.8),(2,-75,.5),(3,-140,.006)]:
            pts=[(120+r[0]*.2,y0+r[col]*ys) for r in rows]
            for u,v in zip(pts,pts[1:]):add_line(draw,const,u,v)
        d.ParametricMode=True
    pre=audit(p,d,draw)
    need(doc.SaveAs(str(out)) is not False,"SaveAs")
    need(out.exists() and zipfile.is_zipfile(out),"Native FRW not produced")
    doc.Close(const.kdDoNotSaveChanges)
    doc=need(app.Documents.Open(str(out),True,False),"Reopen FRW")
    d,view,draw,symbols=setup_doc(api7,doc)
    post=audit(p,d,draw);need(doc.Save() is not False,"Final save");doc.Close(const.kdDoNotSaveChanges)
    doc=need(app.Documents.Open(str(out),True,False),"Final disk reopen")
    d,view,draw,symbols=setup_doc(api7,doc)
    for k in ("l1","L","l3","DX","n","fi"):need(abs(float(var(d,k).Value)-a[k])<1e-5,"Nominal disk state "+k)
    need(str(var(d,"l2").Expression).replace(" ","")==a["l2_expression"],"Final expression")
    doc.Close(const.kdDoNotSaveChanges)
    evidence={"status":"NATIVE_GEOMETRY_TESTS_PASSED_REQUIRES_SCOPE_REVIEW","pre_save":pre,"post_reopen":post,"sha256":hashlib.sha256(out.read_bytes()).hexdigest(),"native_file":out.name}
    out.with_suffix(".verification.json").write_text(json.dumps(evidence,indent=2),encoding="utf-8")
    print(json.dumps(evidence,indent=2))
if __name__=="__main__":main()
