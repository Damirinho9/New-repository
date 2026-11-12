import json, sys, time, ctypes, traceback
from pathlib import Path
from pywinauto.application import Application

PCB=Path(r"C:\Program Files\DipTrace\Pcb.exe")
DIP=Path(sys.argv[1]).resolve()
OUT=Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True,exist_ok=True)
U32=ctypes.windll.user32
WM_COMMAND=0x0111

def wins(app):
    try:return app.windows(visible_only=False,enabled_only=False)
    except:return []

def mainwin(app, timeout=30):
    end=time.time()+timeout
    while time.time()<end:
        for w in wins(app):
            try:
                if w.is_visible() and U32.GetMenu(int(w.handle)) and w.class_name() not in ("#32770","TFMyMessage"):
                    return w
            except:pass
        time.sleep(.2)
    raise RuntimeError("main not found")

def close_startup(app, main):
    for w in wins(app):
        try:
            if w.is_visible() and int(w.handle)!=int(main.handle) and w.class_name()=="TForm92":
                w.close(); time.sleep(.6)
        except:pass

def snap_control(c):
    d={}
    for name,fn in [
        ("text",lambda:c.window_text()),
        ("class",lambda:c.class_name()),
        ("id",lambda:c.control_id()),
        ("visible",lambda:c.is_visible()),
        ("enabled",lambda:c.is_enabled()),
    ]:
        try:d[name]=fn()
        except:d[name]=None
    try:
        r=c.rectangle(); d["rect"]=[r.left,r.top,r.right,r.bottom]
    except:d["rect"]=None
    return d

def dialog_snapshot(d):
    arr=[snap_control(d)]
    try:
        for c in d.descendants(): arr.append(snap_control(c))
    except:pass
    return arr

def invoke_menu(main, top, child):
    menu=main.menu().items()[top].sub_menu()
    item=menu.items()[child]
    info=item.item_info()
    cmd=int(getattr(info,"wID",0) or 0)
    if cmd>0:
        if not U32.PostMessageW(int(main.handle),WM_COMMAND,cmd,0):
            raise RuntimeError("PostMessage failed")
    else:
        item.click()

def visible_dialogs(app,main):
    out=[]
    for w in wins(app):
        try:
            if w.is_visible() and int(w.handle)!=int(main.handle) and w.class_name()!="TApplication":
                out.append(w)
        except:pass
    return out

def close_dialog(d):
    try:
        for c in d.descendants():
            try:
                if c.class_name() in ("Button","TButton") and c.window_text().strip().casefold() in ("cancel","close","ok","отмена","закрыть","ок"):
                    c.click(); time.sleep(.5); return
            except:pass
    except:pass
    try:d.close(); time.sleep(.5)
    except:pass

result={"dip":str(DIP),"verification":[]}
try:
    app=Application(backend="win32").start(f'"{PCB}" "{DIP}"')
    time.sleep(3)
    main=mainwin(app); close_startup(app,main); time.sleep(1)
    result["main_title"]=main.window_text()

    # Design Rules
    invoke_menu(main,7,1); time.sleep(1)
    ds=visible_dialogs(app,main)
    result["design_rules_windows"]=[{"title":d.window_text(),"class":d.class_name(),"controls":dialog_snapshot(d)} for d in ds]
    for d in ds:
        try:
            if "design rules" in d.window_text().casefold():
                d.capture_as_image().save(OUT/"native_rules_dialog.png")
        except:pass
        close_dialog(d)

    # Map remaining Verification commands.
    for idx in range(2,6):
        rec={"index":idx}
        try:
            invoke_menu(main,7,idx); time.sleep(1)
            ds=visible_dialogs(app,main)
            rec["windows"]=[]
            for d in ds:
                rr={"title":d.window_text(),"class":d.class_name(),"controls":dialog_snapshot(d)}
                rec["windows"].append(rr)
                try:d.capture_as_image().save(OUT/f"verification_{idx}_{d.class_name()}.png")
                except:pass
            for d in ds:close_dialog(d)
        except Exception as e:
            rec["error"]=repr(e)
        result["verification"].append(rec)

    try:main.close()
    except:pass
    result["ok"]=True
except Exception as e:
    result["ok"]=False; result["error"]=repr(e); result["traceback"]=traceback.format_exc()
finally:
    (OUT/"native_rules_inspection.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"ok":result.get("ok"),"out":str(OUT)},ensure_ascii=False))
    sys.exit(0 if result.get("ok") else 2)
