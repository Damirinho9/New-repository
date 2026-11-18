# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
import csv, hashlib, math, zipfile
import pythoncom
from win32com.client import Dispatch, gencache

HERE=Path(__file__).resolve().parent
OUT=HERE/"native"
PARAMS=HERE/"parameters.csv"
KOMPAS6_CONSTANTS="{75C9F5D0-B5B8-4526-8681-9903C567D2ED}"
KOMPAS6_API5="{0422828C-F174-495E-AC5D-D31014DBBE87}"

def require(v,msg):
    if not v: raise RuntimeError(msg)
    return v

def constants():
    return gencache.EnsureModule(KOMPAS6_CONSTANTS,0,1,0).constants

def get_kompas5():
    api5=gencache.EnsureModule(KOMPAS6_API5,0,1,0)
    raw=Dispatch("Kompas.Application.5")
    return api5.KompasObject(raw._oleobj_.QueryInterface(api5.KompasObject.CLSID,pythoncom.IID_IDispatch))

def get_kompas7():
    app=Dispatch("KOMPAS.Application.7"); app.Visible=True; return app

def read_params():
    rows={}
    with PARAMS.open(encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f): rows[r["parameter"]]=r
    def val(k): return float(rows[k]["value"])
    return rows,val

def set_name(obj,name):
    for a in ("name","Name"):
        try: setattr(obj,a,name); return
        except Exception: pass

def create_part_doc(kompas,const,path,name):
    path.parent.mkdir(parents=True,exist_ok=True); path.unlink(missing_ok=True)
    doc=require(kompas.Document3D(),f"{name}: Document3D")
    require(doc.Create(False,True),f"{name}: Create")
    part=require(doc.GetPart(const.pTop_Part),f"{name}: top part")
    set_name(part,name)
    return doc,part

def create_sketch(part,const,plane_type,name):
    plane=require(part.GetDefaultEntity(plane_type),f"{name}: default plane")
    sk=require(part.NewEntity(const.o3d_sketch),f"{name}: sketch")
    set_name(sk,name)
    sd=require(sk.GetDefinition(),f"{name}: definition")
    require(sd.SetPlane(plane),f"{name}: SetPlane")
    require(sk.Create(),f"{name}: Create")
    d2=require(sd.BeginEdit(),f"{name}: BeginEdit")
    return sk,sd,d2

def end_sketch(sd):
    r=sd.EndEdit()
    if r is False: raise RuntimeError("EndEdit failed")

def rect_sketch(part,const,y,z,name,cy=0.0,cz=0.0,plane_type=None):
    pt=plane_type or const.o3d_planeYOZ
    sk,sd,d2=create_sketch(part,const,pt,name)
    y0,y1=cy-y/2,cy+y/2; z0,z1=cz-z/2,cz+z/2
    pts=[(y0,z0),(y1,z0),(y1,z1),(y0,z1),(y0,z0)]
    for a,b in zip(pts,pts[1:]):
        require(d2.ksLineSeg(a[0],a[1],b[0],b[1],const.ksCSNormal),f"{name}: line")
    end_sketch(sd); return sk

def circle_sketch(part,const,d,name,cy=0.0,cz=0.0):
    sk,sd,d2=create_sketch(part,const,const.o3d_planeYOZ,name)
    require(d2.ksCircle(cy,cz,d/2,const.ksCSNormal),f"{name}: circle")
    end_sketch(sd); return sk

def annulus_sketch(part,const,od,id_,name):
    sk,sd,d2=create_sketch(part,const,const.o3d_planeYOZ,name)
    require(d2.ksCircle(0,0,od/2,const.ksCSNormal),f"{name}: OD")
    require(d2.ksCircle(0,0,id_/2,const.ksCSNormal),f"{name}: ID")
    end_sketch(sd); return sk

def hex_annulus_sketch(part,const,af,id_,name):
    # regular hex, across-flats = af
    sk,sd,d2=create_sketch(part,const,const.o3d_planeYOZ,name)
    R=af/math.sqrt(3.0)
    pts=[(R*math.cos(math.radians(30+60*i)),R*math.sin(math.radians(30+60*i))) for i in range(6)]
    pts.append(pts[0])
    for a,b in zip(pts,pts[1:]):
        require(d2.ksLineSeg(a[0],a[1],b[0],b[1],const.ksCSNormal),f"{name}: hex")
    require(d2.ksCircle(0,0,id_/2,const.ksCSNormal),f"{name}: bore")
    end_sketch(sd); return sk

def extrusion(part,const,sk,depth,name,boss=False,reverse=False):
    typ=const.o3d_bossExtrusion if boss else const.o3d_baseExtrusion
    e=require(part.NewEntity(typ),f"{name}: entity"); set_name(e,name)
    d=require(e.GetDefinition(),f"{name}: def")
    require(d.SetSketch(sk),f"{name}: sketch")
    d.directionType=const.dtReverse if reverse else const.dtNormal
    require(d.SetSideParam(not reverse,const.etBlind,float(depth),0.0,False),f"{name}: side")
    require(e.Create(),f"{name}: Create"); return e

def cut_extrusion(part,const,sk,depth,name):
    e=require(part.NewEntity(const.o3d_cutExtrusion),f"{name}: entity"); set_name(e,name)
    d=require(e.GetDefinition(),f"{name}: def")
    require(d.SetSketch(sk),f"{name}: sketch"); d.directionType=const.dtNormal
    require(d.SetSideParam(True,const.etBlind,float(depth),0.0,False),f"{name}: side")
    require(e.Create(),f"{name}: Create"); return e

def rotated_profile(part,const,points,name):
    sk,sd,d2=create_sketch(part,const,const.o3d_planeXOY,name)
    xs=[p[0] for p in points]
    require(d2.ksLineSeg(min(xs),0.0,max(xs),0.0,const.ksCSAxis),f"{name}: axis")
    for a,b in zip(points,points[1:]):
        require(d2.ksLineSeg(a[0],a[1],b[0],b[1],const.ksCSNormal),f"{name}: profile")
    end_sketch(sd)
    e=require(part.NewEntity(const.o3d_baseRotated),f"{name}: rotate")
    set_name(e,name+"_REVOLVE")
    dd=require(e.GetDefinition(),f"{name}: rotate def")
    dd.directionType=const.dtNormal
    require(dd.SetSideParam(True,360.0),f"{name}: side")
    require(dd.SetSketch(sk),f"{name}: SetSketch")
    require(e.Create(),f"{name}: Create")
    return e

def save_close(doc,path):
    require(doc.RebuildDocument(),f"{path.name}: rebuild")
    require(doc.SaveAs(str(path)),f"{path.name}: SaveAs")
    try: doc.close()
    except Exception: pass
    native_file(path)

def native_file(path):
    require(path.exists() and path.stat().st_size>1024,f"{path.name}: missing/small")
    require(zipfile.is_zipfile(path),f"{path.name}: not KOMPAS container")
    with zipfile.ZipFile(path) as z:
        names=set(z.namelist())
        require("Contents" in names and "FileInfo" in names,f"{path.name}: container members")

def sha256(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def part_filename(p):
    try: return str(p.GetFileName())
    except Exception: return ""

def placement(part,origin,xaxis=(1,0,0),yaxis=(0,1,0)):
    pl=require(part.GetPlacement(),"GetPlacement")
    require(pl.SetOrigin(*map(float,origin)),"SetOrigin")
    require(pl.SetAxes(*(list(map(float,xaxis))+list(map(float,yaxis)))),"SetAxes")
    require(part.UpdatePlacement(),"UpdatePlacement")

def enumerate_parts(doc):
    coll=require(doc.PartCollection(True),"PartCollection")
    out=[]; seen=set(); n=int(coll.GetCount())
    for i in list(range(n))+list(range(1,n+1)):
        try:p=coll.GetByIndex(i)
        except Exception:p=None
        if not p: continue
        try:key=int(p.reference)
        except Exception:key=id(p)
        if key in seen: continue
        seen.add(key); out.append(p)
    return out

def mate_count(doc):
    c=require(doc.MateConstraintCollection(),"MateConstraintCollection")
    try:c.Refresh()
    except Exception:pass
    return int(c.GetCount())
