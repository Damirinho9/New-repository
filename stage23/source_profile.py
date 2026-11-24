"""Methodology-derived geometry candidate; not native KOMPAS. Fig.8 scheme 1, 13-28."""
import json, math, argparse
from pathlib import Path
import cadquery as cq
from engineering import load, calc
V=cq.Vector

def build(p,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    c=calc(p); r1,r2,r3=[c(k)/2 for k in ('D1','D2','D3')]
    L=c('L_part'); x0=-c('overall_length')+c('cutoff_edge');x5=x0+L
    x1=x0+c('part_l1');x2=x0+c('part_l2');x3=x2+c('part_l3');x4=x5-c('part_l4')
    a=(x3,r2);b=(x4,r1);R=c('R_part');dx=b[0]-a[0];dy=b[1]-a[1];ch=math.hypot(dx,dy);h=math.sqrt(R*R-ch*ch/4)
    cx=(a[0]+b[0])/2-h*dy/ch;cy=(a[1]+b[1])/2+h*dx/ch
    def rr(x):return cy-math.sqrt(max(0,R*R-(x-cx)**2))
    assert abs(rr(x3)-r2)<1e-9 and abs(rr(x4)-r1)<1e-9
    mid=((x3+x4)/2,rr((x3+x4)/2))
    wp=(cq.Workplane('XY').moveTo(x0,0).lineTo(x0,r3).lineTo(x1,r3).lineTo(x2,r2).lineTo(x3,r2).threePointArc(mid,b).lineTo(x5,r1).lineTo(x5,0).close().revolve(360,(0,0),(1,0)).val())
    gamma=math.radians(c('gamma'));alpha=math.radians(c('alpha'));cg=math.cos(gamma);sg=math.sin(gamma)
    Y=c('axis_distance_x'); Z=(Y-r3)*math.tan(alpha)
    def edge(r):
        t=-r3*cg+math.sqrt(r*r-r3*r3*sg*sg)
        return r3+t*cg,-t*sg
    def tool_r(r):
        y,z=edge(r);return math.hypot(y-Y,z-Z)
    sections=[(x0,r3),(x1,r3),(x2,r2),(x3,r2)]
    for i in range(1,math.ceil((x4-x3)/.2)+1):
        x=x3+(x4-x3)*i/math.ceil((x4-x3)/.2); sections.append((x,rr(x)))
    sections.append((x5,r1))
    s2=[(x0,r3),(x1,r3)];n=math.ceil((x2-x1)/.2)
    s2.extend((x1+(x2-x1)*i/n,r3+(r2-r3)*i/n) for i in range(1,n+1));s2.extend(sections[3:]);sections=s2
    rad=[(x,tool_r(r)) for x,r in sections]
    left=-c('overall_length');flange_start=-c('flange_width');f=c('flange_d_adopted')/2
    rleft=rad[0][1];r_right=rad[-1][1];protrusion=3.0;bevel=protrusion*math.tan(math.radians(c('cutoff_angle')))
    ext=[(left,rleft),(left+bevel,rleft+protrusion),(x0-bevel,rleft+protrusion)]+rad+[(flange_start,r_right),(flange_start,f),(0,f)]
    rin=c('d_adopted')/2;rrc=c('mount_recess_d')/2;rt=c('tech_recess_d')/2;re=left+c('mount_recess_length');tech=-p['work2']['tech_recess_length_mm']
    inner=[(0,rin),(tech,rin),(tech,rt),(re,rt),(re,rrc),(left,rrc)]
    blank=cq.Workplane('XY').polyline(ext+inner).close().revolve(360,(0,0),(1,0)).val()
    assert blank.isValid() and len(blank.Solids())==1
    zc=int(c('rifling_z'));beta=math.atan(math.pi/zc);g=V(-math.sin(beta),math.cos(beta),0);normal=V(math.cos(beta),math.sin(beta),0);tan=V(0,0,1)
    origin=V(0,rin,0);lower=.25;upper=1.5;half=upper+lower
    apex=origin-normal*lower;top=origin+normal*upper
    pts=[apex,top-tan*half,top+tan*half];wire=cq.Wire.makePolygon([v-g*3 for v in pts],close=True)
    tool=cq.Solid.extrudeLinear(wire,[],g*((f-rin)/math.cos(beta)+6))
    tools=[tool.rotate((0,0,0),(1,0,0),i*360/zc) for i in range(zc)]
    losses=[blank.intersect(t).Volume() for t in tools];ribbed=blank.cut(*tools)
    assert ribbed.isValid() and min(losses)>0 and max(losses)-min(losses)<1e-5
    d=V(0,cg,-sg);n=V(0,sg,cg);A=V(left-2,r3-Y,-Z)
    tO=(Y-r3)*cg-Z*sg; tstop=tO-(rin+5)
    polygon=[A+d*(-200),A+d*tstop,A+d*tstop+n*250,A+d*(-200)+n*250]
    chip=cq.Solid.extrudeLinear(cq.Wire.makePolygon(polygon,close=True),[],V(c('overall_length')+4,0,0))
    cutter=ribbed.cut(chip);assert cutter.isValid() and len(cutter.Solids())==1
    A2=V(left-2,r3,0);pol2=[A2+d*(-150),A2+d*150,A2+d*150+n*150,A2+d*(-150)+n*150]
    upper_part=cq.Solid.extrudeLinear(cq.Wire.makePolygon(pol2,close=True),[],V(c('overall_length')+4,0,0));sectioned=wp.cut(upper_part)
    assert sectioned.isValid() and len(sectioned.Solids())==1
    checks={}
    for name,s in [('workpiece_full',wp),('workpiece_sectioned',sectioned),('cutter_profile_blank',blank),('cutter_sloped_grooves',ribbed),('cutter_chipspace_candidate',cutter)]:
        path=out/(name+'.step');cq.exporters.export(s,str(path));rs=cq.importers.importStep(str(path)).val();err=abs(rs.Volume()-s.Volume())/s.Volume();checks[name]={'valid':rs.isValid(),'solids':len(rs.Solids()),'volume_mm3':s.Volume(),'roundtrip_relative_error':err};assert rs.isValid() and len(rs.Solids())==1 and err<1e-5,(name,checks[name])
    asm=cq.Assembly(name='Source_guided_candidate');asm.add(sectioned,name='workpiece_sectioned');asm.add(cutter,name='cutter',loc=cq.Location(V(0,Y,Z)));asm.save(str(out/'assembly_source_guided.step'))
    rasm=cq.importers.importStep(str(out/'assembly_source_guided.step')).val();assert rasm.isValid() and len(rasm.Solids())==2
    result={'status':'PASS_INTERMEDIATE_GEOMETRY_ONLY','methodology_compliance':'PARTIAL','native_status':'BLOCKED','source':'KKR fig.8 scheme 1, fig.13-28','beta_deg':math.degrees(beta),'groove_count':zc,'groove_normal_angle_deg':90,'groove_removed_mm3':blank.Volume()-ribbed.Volume(),'chipspace_removed_mm3':ribbed.Volume()-cutter.Volume(),'tool_axis_yz_mm':[Y,Z],'section_samples':len(sections),'checks':checks,'assumptions':['Fig.25 offset directions interpreted in normal plane, not verified against a dimensioned CAD source','Provisional cutoff protrusion and chip-space wall','Small workpiece chamfers, cutter chamfers 1x45 and R2 fillet not modeled','Sampled generatrix approximated by straight segments; native sweep and associative tree pending','No updated native drawing']}
    (out/'source_guided_checks.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
    return result
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--out',required=True);args=a.parse_args();build(load(),args.out)
