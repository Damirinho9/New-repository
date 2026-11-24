"""Independent contract, parameterized OCCT model, and reference checks."""
import argparse,csv,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent
def load(path=HERE/"parameters.json"):
    p=json.loads(Path(path).read_text(encoding="utf-8"))
    assert p["schema"]==1
    a=p["work1"];g=p["work2"]["groove"];c=calc(p)
    assert a["l2_expression"]=="2*L" and all(a[k]>0 for k in ("l1","L","l3","DX","n"))
    assert a["DX"]<a["l3"] and a["L"]>a["l1"]
    assert g["count"]>2 and g["profile_deg"]==90
    assert 0<g["radial_start_mm"]<g["radial_end_mm"] and g["depth_mm"]>0
    assert c("D1")>c("D2")>c("D3")>0
    assert c("d_a_calc")>c("flange_d_adopted")>c("mount_recess_d")>c("tech_recess_d")>c("d_adopted")
    assert c("part_l1")<c("part_l2")<c("part_l2")+c("part_l3")<c("L_part")-c("part_l4")<c("L_part")
    return p
def calc(p):
    m={r["parameter"]:r["value"] for r in p["work2"]["calculation"]}
    return lambda key:float(m[key])
def state(p,deg,L=None):
    a=p["work1"];L=a["L"] if L is None else L;l2=2*L
    t=math.radians(deg);A=(0.,0.);C=(0.,-L)
    B=(a["l1"]*math.cos(t),a["l1"]*math.sin(t));v=(B[0],B[1]+L);r=math.hypot(*v)
    if r<1e-9:raise ValueError("B=C singularity")
    D=(l2*v[0]/r,-L+l2*v[1]/r);q=a["l3"]**2-D[1]**2
    if q<0:raise ValueError("No real slider position")
    E=(D[0]+math.sqrt(q),0.);f=a["DX"]/a["l3"];X=(D[0]+f*(E[0]-D[0]),D[1]*(1-f))
    return A,B,C,D,E,X
def check_mechanics(p):
    a=p["work1"];states=0
    for L,angles in [(a["L"],[i/10 for i in range(3601)]),(20,[45,90,135]),(30,[45,90,135])]:
        for deg in angles:
            A,B,C,D,E,X=state(p,deg,L)
            for x,y,expected in [(A,B,a["l1"]),(A,C,L),(C,D,2*L),(D,E,a["l3"]),(D,X,a["DX"])]:
                assert abs(math.dist(x,y)-expected)<1e-8
            assert abs((B[0]-C[0])*(D[1]-C[1])-(B[1]-C[1])*(D[0]-C[0]))<1e-8
            assert E[1]==0
            states+=1
    try:state(p,270,a["l1"]);raise AssertionError("singularity not rejected")
    except ValueError:pass
    assert all(math.dist(a,b)<1e-8 for a,b in zip(state(p,0),state(p,360)))
    return states
def arc_mid(p1,p2,r):
    x1,y1=p1;x2,y2=p2;dx=x2-x1;dy=y2-y1;c=math.hypot(dx,dy)
    assert 0<c<2*r
    h=math.sqrt(r*r-c*c/4);m=((x1+x2)/2,(y1+y2)/2)
    out=[]
    for sign in (-1,1):
        cx=m[0]-sign*h*dy/c;cy=m[1]+sign*h*dx/c
        a=math.atan2(y1-cy,x1-cx);b=math.atan2(y2-cy,x2-cx)
        t=a+math.remainder(b-a,2*math.pi)/2
        out.append((cx+r*math.cos(t),cy+r*math.sin(t)))
    return max(out,key=lambda x:x[1])
def models(p,out):
    import cadquery as cq
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    c=calc(p);g=p["work2"]["groove"];L=c("L_part");x0=-L
    x1=x0+c("part_l1");x2=x0+c("part_l2");x3=x2+c("part_l3");x4=-c("part_l4")
    r1,r2,r3=[c(k)/2 for k in ("D1","D2","D3")]
    mid=arc_mid((x3,r2),(x4,r1),c("R_part"))
    workpiece=(cq.Workplane("XY").moveTo(x0,0).lineTo(x0,r3).lineTo(x1,r3).lineTo(x2,r2).lineTo(x3,r2).threePointArc(mid,(x4,r1)).lineTo(0,r1).lineTo(0,0).close().revolve(360,(0,0),(1,0)).val())
    left=-c("overall_length");re=left+c("mount_recess_length");right=-c("flange_width");tech=right-p["work2"]["tech_recess_length_mm"]
    rin,rout,rf,rr,rt=[c(k)/2 for k in ("d_adopted","d_a_calc","flange_d_adopted","mount_recess_d","tech_recess_d")]
    q=[(left,rr),(re,rr),(re,rin),(tech,rin),(tech,rt),(right,rt),(right,rin),(0,rin),(0,rf),(right,rf),(right,rout),(left,rout)]
    blank=cq.Workplane("XY").polyline(q).close().revolve(360,(0,0),(1,0)).val()
    dep=g["depth_mm"];over=g["axial_tool_overrun_mm"];start=g["radial_start_mm"];end=g["radial_end_mm"]
    width=(dep+over)*math.tan(math.radians(g["profile_deg"]/2))
    wire=cq.Wire.makePolygon([cq.Vector(-dep,start,0),cq.Vector(over,start,-width),cq.Vector(over,start,width)],close=True)
    tool=cq.Solid.extrudeLinear(wire,[],cq.Vector(0,end-start,0))
    tools=[tool.rotate((0,0,0),(1,0,0),i*360/g["count"]) for i in range(g["count"])]
    losses=[blank.intersect(t).Volume() for t in tools]
    ribbed=blank.cut(*tools)
    shift=cq.Vector(0,c("axis_distance_x"),(c("axis_distance_x")-c("D3")/2)*math.tan(math.radians(c("alpha"))))
    cutter=ribbed.cut(workpiece.translate(-shift))
    moved=ribbed.cut(workpiece.translate(cq.Vector(0,5,0)-shift))
    assert min(losses)>0 and max(losses)-min(losses)<1e-5
    assert math.isclose(blank.Volume()-ribbed.Volume(),sum(losses),rel_tol=1e-6)
    assert abs(moved.Volume()-cutter.Volume())>1
    for name,s in [("workpiece",workpiece),("blank_v90_candidate",ribbed),("cutter_v90_candidate",cutter)]:
        assert s.isValid() and len(s.Solids())==1
        path=out/(name+".step");cq.exporters.export(s,str(path));re=cq.importers.importStep(str(path)).val()
        assert re.isValid() and len(re.Solids())==1 and math.isclose(re.Volume(),s.Volume(),rel_tol=1e-7)
    asm=cq.Assembly(name="V19_candidate");asm.add(workpiece,name="workpiece");asm.add(cutter,name="cutter",loc=cq.Location(shift));asm.save(str(out/"assembly_candidate.step"))
    re=cq.importers.importStep(str(out/"assembly_candidate.step")).val();assert re.isValid() and len(re.Solids())==2
    section=cq.Workplane("XY",obj=cutter).section().val()
    area=sum(f.Area() for f in section.Faces());assert area>0
    res={"status":"PASS_INTERMEDIATE","native_status":"BLOCKED","candidate_only":True,"workpiece_volume_mm3":workpiece.Volume(),"blank_volume_mm3":blank.Volume(),"cutter_volume_mm3":cutter.Volume(),"groove_removed_mm3":blank.Volume()-ribbed.Volume(),"dependency_delta_mm3":moved.Volume()-cutter.Volume(),"section_area_mm2":area,"kinematic_checks":check_mechanics(p)}
    for key in ("workpiece_volume_mm3","cutter_volume_mm3","groove_removed_mm3"):
        assert math.isclose(res[key],p["reference"][key],rel_tol=2e-6), (key,res[key],p["reference"][key])
    (out/"independent.json").write_text(json.dumps(res,indent=2))
    return res
if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--out",default="engineering-output");ap.add_argument("--parameters",default=str(HERE/"parameters.json"));a=ap.parse_args()
    print(json.dumps(models(load(a.parameters),a.out),indent=2))
