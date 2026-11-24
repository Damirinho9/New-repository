"""Independent V90 candidate smoke test; no KOMPAS licensing or native acceptance."""
import math,json
from pathlib import Path
import cadquery as cq
import ezdxf
out=Path("stage18-output");out.mkdir(exist_ok=True)
for i in range(3601):
    p=math.radians(i/10);bx=20*math.cos(p);by=20*math.sin(p)
    r=math.hypot(bx,by+25);dx=50*bx/r;dy=-25+50*(by+25)/r
    ex=dx+math.sqrt(3600-dy*dy)
    assert abs(math.hypot(dx,dy+25)-50)<1e-8
    assert abs(math.hypot(ex-dx,dy)-60)<1e-8
q=[(-89,40),(-74,40),(-74,32.5),(-20,32.5),(-20,33.5),(-5,33.5),(-5,32.5),(0,32.5),(0,50),(-5,50),(-5,90.5),(-89,90.5)]
blank=cq.Workplane("XY").polyline(q).close().revolve(360,(0,0),(1,0)).val()
w=cq.Wire.makePolygon([cq.Vector(-1.5,40.25,0),cq.Vector(.25,40.25,-1.75),cq.Vector(.25,40.25,1.75)],close=True)
tool=cq.Solid.extrudeLinear(w,[],cq.Vector(0,10.25,0))
tools=[tool.rotate((0,0,0),(1,0,0),i*11.25) for i in range(32)]
losses=[blank.intersect(t).Volume() for t in tools]
candidate=blank.cut(*tools)
assert candidate.isValid() and len(candidate.Solids())==1
assert min(losses)>0 and max(losses)-min(losses)<1e-5
assert math.isclose(blank.Volume()-candidate.Volume(),sum(losses),rel_tol=1e-6)
p=out/"blank-v90-candidate.step"
cq.exporters.export(candidate,str(p))
r=cq.importers.importStep(str(p)).val()
assert r.isValid() and math.isclose(r.Volume(),candidate.Volume(),rel_tol=1e-6)
sec=cq.Workplane("XY",obj=candidate).section().val()
assert sum(f.Area() for f in sec.Faces())>0
d=ezdxf.new("R2010");d.units=4;m=d.modelspace()
for face in sec.Faces():
    for wire in face.Wires():
        n=max(24,int(wire.Length()/.5))
        m.add_lwpolyline([(v.x,v.y) for v in (wire.positionAt(k/n) for k in range(n))],close=True)
d.saveas(out/"blank-section.dxf")
assert not ezdxf.readfile(out/"blank-section.dxf").audit().errors
(out/"checks.json").write_text(json.dumps({"status":"PASS_INTERMEDIATE","native":"BLOCKED","candidate_only":True,"kinematic_states":3601,"grooves":32,"removed_volume_mm3":blank.Volume()-candidate.Volume(),"section_area_mm2":sum(f.Area() for f in sec.Faces())},indent=2))
