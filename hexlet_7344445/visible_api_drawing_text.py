from __future__ import annotations
import hashlib, json, pathlib, sys, time, traceback
sys.path.append('/opt/ascon/kompas3d-v25/Bin')
from constants import constants as c
import ksapi

OUT=pathlib.Path("visible_api")
OUT.mkdir(exist_ok=True)
target=(OUT/"Hexlet_KOMPAS3D_Privet_Hexlet.cdw").resolve()

try:
    ksapi.SetKompasPath('/opt/ascon/kompas3d-v25/Bin')
except Exception as exc:
    print("SET_PATH_WARN",type(exc).__name__,str(exc))

try:
    app=ksapi.OpenKompas()
    print("APP",app)
    if app is None:
        raise RuntimeError("OpenKompas returned None")
    app.SetVisible(True)
    print("APP_NAME",app.GetApplicationName(True))
    print("BUILD",app.GetBuildNumber())

    docs=app.GetDocuments()
    print("DOCS",docs)
    if docs is None:
        raise RuntimeError("GetDocuments returned None")

    doc=docs.AddWithDefaultSettings(c.ksDocumentDrawing,True)
    print("ADD_DEFAULT",doc)
    if doc is None:
        try:
            err=app.GetKompasError()
            print("KOMPAS_ERROR",err)
        except Exception as exc:
            print("ERROR_QUERY_WARN",type(exc).__name__,str(exc))
        raise RuntimeError("visible AddWithDefaultSettings drawing returned None")

    d2=ksapi.IKompasDocument2D(doc)
    view=d2.GetViewsAndLayersManager().GetViews().GetActiveView()
    dc=ksapi.IDrawingContainer(view)
    texts=dc.GetDrawingTexts()
    print("TEXT_COUNT_BEFORE",texts.GetCount())

    t=texts.Add()
    print("TEXT_OBJ",t)
    if t is None:
        raise RuntimeError("DrawingTexts.Add returned None")
    t.SetX(70.0); t.SetY(120.0)
    it=ksapi.IText(t)
    line=it.Add()
    print("TEXT_LINE",line)
    if line is None:
        raise RuntimeError("IText.Add returned None")
    item=line.Add()
    print("TEXT_ITEM",item)
    if item is None:
        raise RuntimeError("line.Add returned None")
    item.SetStr("Привет, Хекслет!")
    try:
        ksapi.ITextFont(item).SetHeight(10.0)
    except Exception as exc:
        print("FONT_WARN",type(exc).__name__,str(exc))
    upd=t.Update()
    print("TEXT_UPDATE",upd)
    if not upd:
        raise RuntimeError("DrawingText.Update false")
    print("TEXT_COUNT_AFTER",texts.GetCount())

    ok=doc.SaveAs(str(target))
    print("SAVEAS",ok)
    if not target.exists() or target.stat().st_size==0:
        raise RuntimeError("native CDW not saved")
    print("SIZE",target.stat().st_size)
    print("SHA256",hashlib.sha256(target.read_bytes()).hexdigest())

    (OUT/"READY").write_text("PASS\n",encoding="utf-8")
    print("RESULT=PASS_VISIBLE_API_NATIVE_TEXT")
    sys.stdout.flush()

    # Keep real visible KOMPAS alive for screenshot inspection.
    time.sleep(90)
except Exception as exc:
    traceback.print_exc()
    (OUT/"FAIL").write_text(type(exc).__name__+": "+str(exc)+"\n",encoding="utf-8")
    print("RESULT=FAIL_VISIBLE_API_NATIVE_TEXT",type(exc).__name__,str(exc))
    sys.stdout.flush()
    time.sleep(10)
    raise
