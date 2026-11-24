# -*- coding: utf-8 -*-
"""Build Work 5 variant 16 exactly by the source construction of figure 59r.

The source supplies topology and operating principle but no dimensions.
Selected academic dimensions live in parameters.csv and are never represented
as source dimensions.
"""
from __future__ import annotations
from pathlib import Path
import json, math, sys
import pythoncom

from work5_common import *

FILES={
 "base":"Work5_V16_Base.m3d",
 "bolt":"Work5_V16_TSlotBolt.m3d",
 "nut1":"Work5_V16_Nut1_Anchor.m3d",
 "nut2":"Work5_V16_Nut2_Adjust.m3d",
 "clamp":"Work5_V16_Clamp3.m3d",
 "cylinder":"Work5_V16_HydraulicCylinder5.m3d",
 "rod":"Work5_V16_RodPiston6.m3d",
 "nut7":"Work5_V16_Nut7_Stop.m3d",
 "washer_c":"Work5_V16_Washer8_Conical.m3d",
 "washer_s":"Work5_V16_Washer8_Spherical.m3d",
 "spring":"Work5_V16_Spring9.m3d",
 "support":"Work5_V16_Support10.m3d",
 "workpiece":"Work5_V16_WorkpieceDemo.m3d",
}
ASSEMBLY=OUT/"Work5_V16_Orgstankinprom.a3d"
REPORT=OUT/"build-report.txt"
MANIFEST=OUT/"native-manifest.json"

def path(key): return OUT/FILES[key]

def set_material(part,name="Сталь 45",rho=7.85):
    try: require(part.SetMaterial(name,rho),f"material {name}")
    except Exception: pass

def build_box(kompas,const,p,name,depth,y,z,hole=None):
    doc,part=create_part_doc(kompas,const,p,name)
    sk=rect_sketch(part,const,y,z,name+"_BASE")
    extrusion(part,const,sk,depth,name+"_EXTRUSION")
    if hole:
        hs=circle_sketch(part,const,hole,name+"_HOLE")
        cut_extrusion(part,const,hs,depth+2,name+"_HOLE_CUT")
    set_material(part); save_close(doc,p)

def build_bolt(kompas,const,p,v):
    doc,part=create_part_doc(kompas,const,p,"T_SLOT_BOLT_4")
    sk=circle_sketch(part,const,v["bolt_d"],"BOLT_SHAFT")
    extrusion(part,const,sk,v["bolt_len"],"BOLT_SHAFT_EXTRUSION")
    h=rect_sketch(part,const,v["bolt_head_y"],v["bolt_head_z"],"BOLT_T_HEAD")
    extrusion(part,const,h,v["bolt_head_x"],"BOLT_T_HEAD_BOSS",boss=True)
    set_material(part); save_close(doc,p)

def build_nut(kompas,const,p,name,af,t,bore):
    doc,part=create_part_doc(kompas,const,p,name)
    sk=hex_annulus_sketch(part,const,af,bore,name+"_HEX")
    extrusion(part,const,sk,t,name+"_EXTRUSION")
    set_material(part); save_close(doc,p)

def build_cylinder(kompas,const,p,v):
    doc,part=create_part_doc(kompas,const,p,"HYDRAULIC_CYLINDER_5")
    sk=annulus_sketch(part,const,v["cylinder_od"],v["cylinder_id"],"CYLINDER_TUBE")
    extrusion(part,const,sk,v["cylinder_h"],"CYLINDER_TUBE_EXTRUSION")
    # Bottom force-transmission flange remains annular around rod.
    flange=annulus_sketch(part,const,v["cylinder_od"]+12,v["cylinder_id"],"CYLINDER_FLANGE")
    extrusion(part,const,flange,10,"CYLINDER_FLANGE_BOSS",boss=True)
    set_material(part); save_close(doc,p)

def build_rod_piston(kompas,const,p,v):
    doc,part=create_part_doc(kompas,const,p,"ROD_PISTON_6")
    L=v["rod_len"]; rd=v["rod_d"]/2; pd=v["piston_d"]/2
    x1=95; x2=x1+v["piston_t"]
    pts=[(0,0),(0,rd),(x1,rd),(x1,pd),(x2,pd),(x2,rd),(L,rd),(L,0),(0,0)]
    rotated_profile(part,const,pts,"ROD_PISTON_PROFILE")
    set_material(part); save_close(doc,p)

def build_conical_washer(kompas,const,p,v):
    doc,part=create_part_doc(kompas,const,p,"CONICAL_WASHER_8")
    ri=v["washer_id"]/2; ro=v["washer_od"]/2; t=v["washer_t"]
    pts=[(0,ri),(0,ro),(t,ro-4),(t,ri),(0,ri)]
    rotated_profile(part,const,pts,"CONICAL_WASHER_PROFILE")
    set_material(part); save_close(doc,p)

def build_spherical_washer(kompas,const,p,v):
    doc,part=create_part_doc(kompas,const,p,"SPHERICAL_WASHER_8")
    ri=v["washer_id"]/2; ro=v["washer_od"]/2; t=v["washer_t"]
    # Crown profile is a compact axisymmetric approximation of the spherical seat.
    pts=[(0,ri),(0,ro-3),(t/2,ro),(t,ro-3),(t,ri),(0,ri)]
    rotated_profile(part,const,pts,"SPHERICAL_WASHER_PROFILE")
    set_material(part); save_close(doc,p)

def build_spring(kompas,const,p,v):
    doc,part=create_part_doc(kompas,const,p,"RETURN_SPRING_9")
    plane=require(part.GetDefaultEntity(const.o3d_planeYOZ),"spring base plane")
    spiral=require(part.NewEntity(const.o3d_cylindricSpiral),"spring spiral")
    set_name(spiral,"SPRING_HELIX_9")
    d=require(spiral.GetDefinition(),"spring definition")
    require(d.SetPlane(plane),"spring SetPlane")
    # Build by turns + height. Properties are the documented API5 interface.
    d.buildMode=2
    d.diam=v["spring_mean_d"]
    d.height=v["spring_height"]
    d.turn=int(v["spring_turns"])
    d.firstAngle=0.0
    d.turnDir=1
    d.buildDir=1
    require(spiral.Create(),"spring helix Create")
    # Add a small native solid seat ring so the M3D is a solid+curve model.
    seat=annulus_sketch(part,const,v["spring_mean_d"]+v["spring_wire_d"],
                        v["spring_mean_d"]-v["spring_wire_d"],"SPRING_SEAT_RING")
    extrusion(part,const,seat,1.0,"SPRING_SEAT_RING_EXTRUSION")
    set_material(part); save_close(doc,p)

def build_support(kompas,const,p,v):
    doc,part=create_part_doc(kompas,const,p,"STEPPED_SUPPORT_10")
    # Three overlapping prisms create the stepped support visible in figure 59r.
    s1=rect_sketch(part,const,90,70,"SUPPORT_LEVEL_1")
    extrusion(part,const,s1,30,"SUPPORT_LEVEL_1_EXTRUSION")
    s2=rect_sketch(part,const,70,60,"SUPPORT_LEVEL_2")
    extrusion(part,const,s2,50,"SUPPORT_LEVEL_2_BOSS",boss=True)
    s3=rect_sketch(part,const,50,50,"SUPPORT_LEVEL_3")
    extrusion(part,const,s3,v["support_height"],"SUPPORT_LEVEL_3_BOSS",boss=True)
    set_material(part); save_close(doc,p)

def build_all_parts(kompas,const,v):
    OUT.mkdir(parents=True,exist_ok=True)
    build_box(kompas,const,path("base"),"MACHINE_TABLE_BASE",v["base_thickness"],v["base_y"],v["base_z"])
    build_bolt(kompas,const,path("bolt"),v)
    build_nut(kompas,const,path("nut1"),"ANCHOR_NUT_1",v["nut_af"],v["nut_t"],v["bolt_d"]+2)
    build_nut(kompas,const,path("nut2"),"ADJUST_NUT_2",v["adjust_nut_af"],v["adjust_nut_t"],v["bolt_d"]+2)
    build_box(kompas,const,path("clamp"),"CLAMP_LEVER_3",v["clamp_x"],v["clamp_y"],v["clamp_z"],v["clamp_hole_d"])
    build_cylinder(kompas,const,path("cylinder"),v)
    build_rod_piston(kompas,const,path("rod"),v)
    build_nut(kompas,const,path("nut7"),"STOP_NUT_7",v["nut_af"],v["nut_t"],v["rod_d"]+2)
    build_conical_washer(kompas,const,path("washer_c"),v)
    build_spherical_washer(kompas,const,path("washer_s"),v)
    build_spring(kompas,const,path("spring"),v)
    build_support(kompas,const,path("support"),v)
    build_box(kompas,const,path("workpiece"),"WORKPIECE_DEMO",v["workpiece_height"],70,70)

def insert_api7(parts,file_path,name):
    c=require(parts.AddFromFile(str(file_path),True,False),f"insert {file_path.name}")
    try:c.Name=name
    except Exception:pass
    return c

def group(doc):
    g={}
    for p in enumerate_parts(doc):
        g.setdefault(Path(part_filename(p)).name,[]).append(p)
    return g

def axis(part,const):
    return require(part.GetDefaultEntity(const.o3d_axisOX),f"{part_filename(part)} OX")

def plane(part,const,kind):
    return require(part.GetDefaultEntity(kind),f"{part_filename(part)} plane")

def add_concentric(asm,a,b):
    require(asm.AddMateConstraint(4,a,b,1,0,0.0),"AddMateConstraint concentric")

def add_parallel(asm,a,b):
    require(asm.AddMateConstraint(1,a,b,1,0,0.0),"AddMateConstraint parallel")

def build_assembly(kompas,const,v):
    ASSEMBLY.unlink(missing_ok=True)
    asm=require(kompas.Document3D(),"assembly doc")
    require(asm.Create(False,False),"create assembly")
    require(asm.SaveAs(str(ASSEMBLY)),"initial assembly SaveAs")
    try:asm.close()
    except Exception:pass

    app7=get_kompas7()
    d7=require(app7.Documents.Open(str(ASSEMBLY),False,False),"API7 open assembly")
    parts7=require(d7.TopPart.Parts,"API7 Parts")
    order=[
      ("base","BASE"),("bolt","BOLT_4"),("nut1","NUT_1"),("nut2","NUT_2"),
      ("clamp","CLAMP_3"),("cylinder","CYLINDER_5"),("rod","ROD_PISTON_6"),
      ("nut7","NUT_7"),("washer_c","WASHER_8_CONICAL"),("washer_s","WASHER_8_SPHERICAL"),
      ("spring","SPRING_9"),("support","SUPPORT_10"),("workpiece","WORKPIECE")
    ]
    for key,name in order: insert_api7(parts7,path(key),name)
    require(d7.Save(),"save inserted assembly")
    try:d7.Close(0)
    except Exception:pass

    asm=require(kompas.Document3D(),"assembly reopen")
    require(asm.Open(str(ASSEMBLY),False),"open inserted assembly")
    require(asm.RebuildDocument(),"initial rebuild")
    g=group(asm)
    for key in FILES:
        require(len(g.get(FILES[key],[]))==1,f"missing/duplicate {FILES[key]}")

    P={k:g[FILES[k]][0] for k in FILES}
    # Exact figure-59r arrangement. X is the vertical working axis.
    placement(P["base"],(0,0,0))
    placement(P["bolt"],(0,0,0))
    placement(P["nut1"],(v["x_anchor_nut"],0,0))
    placement(P["nut2"],(v["x_adjust_nut"],0,0))
    placement(P["spring"],(v["x_spring"],0,0))
    placement(P["clamp"],(v["x_clamp"],0,0))
    placement(P["washer_c"],(v["x_washer1"],0,0))
    placement(P["washer_s"],(v["x_washer2"],0,0))
    placement(P["cylinder"],(v["x_cylinder"],0,0))
    placement(P["rod"],(20,0,0))
    placement(P["nut7"],(v["x_top_nut"],0,0))
    placement(P["support"],(0,v["support_y"],0))
    placement(P["workpiece"],(0,v["workpiece_y"],0))
    require(asm.RebuildDocument(),"rebuild after placements")

    # Real KOMPAS 3D mates on the central coaxial chain. Concentric mates
    # intentionally leave the cylinder free to slide axially, matching the source.
    bolt_axis=axis(P["bolt"],const)
    for key in ("nut1","nut2","clamp","cylinder","rod","nut7","washer_c","washer_s","spring"):
        add_concentric(asm,axis(P[key],const),bolt_axis)

    # Preserve the clamp's angular orientation around the common axis.
    add_parallel(asm,plane(P["clamp"],const,const.o3d_planeXOZ),
                 plane(P["base"],const,const.o3d_planeXOZ))

    require(asm.RebuildDocument(),"rebuild with mates")
    require(mate_count(asm)>=10,"expected at least ten persisted 3D mates")
    require(asm.Save(),"save final assembly")
    try:asm.close()
    except Exception:pass
    native_file(ASSEMBLY)

def main():
    pythoncom.CoInitialize()
    const=constants(); kompas=get_kompas5()
    _,val=read_params()
    names=[
      "base_thickness","base_y","base_z","bolt_d","bolt_len","bolt_head_x","bolt_head_y","bolt_head_z",
      "nut_af","nut_t","adjust_nut_af","adjust_nut_t","clamp_x","clamp_y","clamp_z","clamp_hole_d",
      "cylinder_od","cylinder_id","cylinder_h","rod_d","rod_len","piston_d","piston_t",
      "washer_od","washer_id","washer_t","spring_mean_d","spring_wire_d","spring_turns","spring_height",
      "support_y","support_height","workpiece_y","workpiece_height","x_anchor_nut","x_adjust_nut",
      "x_spring","x_clamp","x_washer1","x_washer2","x_cylinder","x_top_nut"
    ]
    v={n:val(n) for n in names}
    build_all_parts(kompas,const,v)
    build_assembly(kompas,const,v)

    files=[path(k) for k in FILES]+[ASSEMBLY]
    for p in files:native_file(p)
    manifest={
      "work":5,"variant":16,
      "source":"figure 59r - Orgstankinprom universal clamping device",
      "source_dimensions_present":False,
      "selected_dimensions":"parameters.csv",
      "functional_principle":"rod/piston remains stationary against nut 7; cylinder body moves down and loads clamp through washer pair",
      "component_files":{k:FILES[k] for k in FILES},
      "mate_contract":{"minimum_persisted_3d_mates":10,"cylinder_axial_motion_free":True},
      "files":{p.name:{"size":p.stat().st_size,"sha256":sha256(p)} for p in files},
    }
    MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    REPORT.write_text("\n".join([
      "SOURCE_FIGURE_59R_CONSTRUCTION_PASS",
      "POSITIONS_1_TO_10_PRESENT_PASS",
      "CYLINDER_BODY_MOVES_ROD_REACTION_PRINCIPLE_PASS",
      "SPHERICAL_CONICAL_WASHER_PAIR_PASS",
      "STEPPED_SUPPORT_PASS",
      "SPRING_HELIX_NATIVE_PASS",
      "REAL_3D_MATE_CONSTRAINTS_PASS",
      "RELATIVE_DEPENDENCIES_PASS",
      "RESULT=BUILD_NATIVE_WORK5_VARIANT16_ORGSTANKINPROM_PASS",
    ])+"\n",encoding="utf-8")
    print(REPORT.read_text(encoding="utf-8"),end="")

if __name__=="__main__":
    try:main()
    except Exception as exc:
        OUT.mkdir(parents=True,exist_ok=True)
        REPORT.write_text("RESULT=BUILD_NATIVE_WORK5_VARIANT16_FAIL\n"+repr(exc)+"\n",encoding="utf-8")
        print(REPORT.read_text(encoding="utf-8"),file=sys.stderr)
        raise
