# -*- coding: utf-8 -*-
from pathlib import Path
import hashlib, math, zipfile
import ksapi
from constants import constants as c

OUT=Path("work4_deb_native3d_probe.m3d").resolve()
LOG=Path("work4_deb_native3d_probe.txt")

def req(v,msg):
    if not v: raise RuntimeError(msg)
    return v

def dc_from_frag(frag):
    vm=req(frag.GetViewsAndLayersManager(),"views manager")
    views=req(vm.GetViews(),"views")
    view=req(views.GetActiveView(),"active view")
    return ksapi.IDrawingContainer(view)

def add_rect(frag,w,h):
    dc=dc_from_frag(frag)
    lines=req(dc.GetLineSegments(),"lines")
    x0,x1=-w/2,w/2; y0,y1=-h/2,h/2
    for x1_,y1_,x2_,y2_ in [(x0,y0,x1,y0),(x1,y0,x1,y1),(x1,y1,x0,y1),(x0,y1,x0,y0)]:
        s=req(lines.Add(),"line add")
        s.SetX1(x1_); s.SetY1(y1_); s.SetX2(x2_); s.SetY2(y2_)
        s.SetStyle(c.ksCSNormal)
        req(s.Update(),"line update")

def mass(top):
    m=float(top.GetMass())
    req(math.isfinite(m) and m>0,f"bad mass {m}")
    return m

def main():
    lines=[]
    app=req(ksapi.GetKompas(),"GetKompas None")
    lines.append("GET_KOMPAS_PASS")
    docs=req(app.GetDocuments(),"Documents")
    OUT.unlink(missing_ok=True)

    base=req(docs.Add(c.ksDocumentPart, True),"Documents.Add part")
    d3=ksapi.IKompasDocument3D(base)
    top=req(d3.GetTopPart(),"TopPart")
    mc=req(top.GetModelContainer(),"ModelContainer")
    sketches=req(mc.GetSketchs(),"Sketchs")
    sk=req(sketches.Add(),"Sketch Add")
    sk.SetName("NATIVE3D_PROBE_SKETCH")
    plane=req(top.GetDefaultObject(c.o3d_planeXOY),"XOY")
    sk.SetPlane(plane)
    req(sk.Update(),"sketch placement update")
    frag=req(sk.BeginEdit(False),"BeginEdit")
    add_rect(frag,20.0,12.0)
    req(sk.EndEdit(),"EndEdit")
    req(sk.Update(),"sketch update")
    lines.append("CREATE_SKETCH_PASS")

    exts=req(mc.GetExtrusions(),"Extrusions")
    ext=req(exts.Add(c.o3d_baseExtrusion),"Extrusion Add")
    ext.SetName("NATIVE3D_PROBE_EXTRUSION")
    ext.SetProfiles([sk])
    req(ext.SetSideParameters(True,c.etBlind,10.0,0.0,False,None),"SetSideParameters 10")
    req(ext.Update(),"extrusion update")
    req(top.RebuildModel(False),"top rebuild")
    req(d3.RebuildDocument(),"doc rebuild")
    m10=mass(top)
    lines.append(f"MASS_10={m10:.12f}")
    lines.append("CREATE_EXTRUSION_PASS")

    req(base.SaveAs(str(OUT)),"SaveAs")
    req(OUT.exists() and OUT.stat().st_size>1024,"saved file absent/small")
    req(zipfile.is_zipfile(OUT),"not zip native container")
    with zipfile.ZipFile(OUT) as z:
        req({"Contents","FileInfo"}.issubset(set(z.namelist())),"Contents/FileInfo missing")
    lines.append("SAVE_AS_NATIVE_PASS")
    base.Close(c.kdDoNotSaveChanges)

    rb=req(docs.Open(str(OUT),True,False),"reopen")
    rd3=ksapi.IKompasDocument3D(rb)
    rtop=req(rd3.GetTopPart(),"reopened top")
    req(rd3.RebuildDocument(),"reopen doc rebuild")
    req(rtop.RebuildModel(False),"reopen top rebuild")
    rmc=req(rtop.GetModelContainer(),"reopen model container")
    rexts=req(rmc.GetExtrusions(),"reopen extrusions")
    req(rexts.GetCount()>=1,"no persisted extrusion")
    rext=req(rexts.GetExtrusion(0),"GetExtrusion(0)")
    m10r=mass(rtop)
    req(abs(m10r-m10)<=max(1e-6,m10*1e-6),"reopen nominal mass drift")
    lines.append("REOPEN_REBUILD_PASS")

    req(rext.SetSideParameters(True,c.etBlind,14.0,0.0,False,None),"mutate depth 14")
    req(rext.Update(),"mutate update")
    req(rtop.RebuildModel(False),"mutate top rebuild")
    req(rd3.RebuildDocument(),"mutate doc rebuild")
    m14=mass(rtop)
    req(m14>m10r*1.2,f"physical mass did not increase {m10r}->{m14}")
    lines.append(f"MASS_14={m14:.12f}")
    lines.append("PHYSICAL_3D_MUTATION_PASS")
    req(rb.Save(),"save changed")
    rb.Close(c.kdDoNotSaveChanges)

    cb=req(docs.Open(str(OUT),True,False),"reopen changed")
    cd3=ksapi.IKompasDocument3D(cb); ctop=req(cd3.GetTopPart(),"changed top")
    req(cd3.RebuildDocument(),"changed doc rebuild"); req(ctop.RebuildModel(False),"changed top rebuild")
    cm=mass(ctop)
    req(abs(cm-m14)<=max(1e-6,m14*1e-6),"changed state not persisted")
    lines.append("MUTATED_SAVE_CLOSE_REOPEN_PASS")
    cext=req(ctop.GetModelContainer().GetExtrusions().GetExtrusion(0),"changed extrusion")
    req(cext.SetSideParameters(True,c.etBlind,10.0,0.0,False,None),"restore depth")
    req(cext.Update(),"restore update"); req(ctop.RebuildModel(False),"restore top rebuild"); req(cd3.RebuildDocument(),"restore doc rebuild")
    mr=mass(ctop); req(abs(mr-m10)<=max(1e-6,m10*1e-6),"restore mass drift")
    req(cb.Save(),"save restored"); cb.Close(c.kdDoNotSaveChanges)

    fb=req(docs.Open(str(OUT),True,False),"final reopen")
    fd3=ksapi.IKompasDocument3D(fb); ftop=req(fd3.GetTopPart(),"final top")
    req(fd3.RebuildDocument(),"final doc rebuild"); req(ftop.RebuildModel(False),"final top rebuild")
    mf=mass(ftop); req(abs(mf-m10)<=max(1e-6,m10*1e-6),"final mass drift")
    fb.Close(c.kdDoNotSaveChanges)
    lines.append("FINAL_NOMINAL_REOPEN_PASS")
    lines.append("SHA256="+hashlib.sha256(OUT.read_bytes()).hexdigest())
    lines.append("RESULT=RUNTIME_NATIVE_3D_MUTATION_PASS")
    LOG.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(LOG.read_text(encoding="utf-8"),end="")

if __name__=="__main__":
    try: main()
    except Exception as e:
        LOG.write_text("RESULT=RUNTIME_NATIVE_3D_MUTATION_FAIL\n"+repr(e)+"\n",encoding="utf-8")
        print(LOG.read_text(encoding="utf-8"),end="")
        raise
