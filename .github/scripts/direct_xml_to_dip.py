import ctypes, json, sys, time, traceback, hashlib
from pathlib import Path
from pywinauto.application import Application

PCB=Path(r"C:\Program Files\DipTrace\Pcb.exe")
SRC=Path(sys.argv[1]).resolve()
DIP=Path(sys.argv[2]).resolve()
OUT=Path(sys.argv[3]).resolve()
OUT.mkdir(parents=True,exist_ok=True)
U32=ctypes.windll.user32
WM_COMMAND=0x0111
E={"source":str(SRC),"dip":str(DIP),"steps":[],"ok":False}

def step(name,**kw):
    E["steps"].append({"name":name,**kw}); print(name,kw,flush=True)

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def wins(app):
    try:return app.windows(visible_only=False,enabled_only=False)
    except:return []

def mainwin(app,timeout=30):
    end=time.time()+timeout
    while time.time()<end:
        for w in wins(app):
            try:
                if w.is_visible() and U32.GetMenu(int(w.handle)) and w.class_name() not in ("#32770","TFMyMessage","TApplication"):
                    return w
            except:pass
        time.sleep(.2)
    raise RuntimeError("main window not found")

def dismiss_startup(app,main):
    for _ in range(8):
        found=False
        for w in wins(app):
            try:
                if w.is_visible() and int(w.handle)!=int(main.handle) and w.class_name() in ("TForm92","TFMyMessage"):
                    txt=" ".join([w.window_text()]+[c.window_text() for c in w.descendants()[:80]])
                    if "error" in txt.casefold(): raise RuntimeError("startup error: "+txt)
                    for c in w.descendants():
                        try:
                            if c.class_name() in ("Button","TButton") and c.window_text().strip().casefold() in ("ok","&ok","yes","&yes"):
                                c.click();found=True;break
                        except:pass
                    if not found:
                        w.close();found=True
                    time.sleep(.5)
            except RuntimeError: raise
            except: pass
        if not found: break

def invoke(main,top,child):
    root=U32.GetMenu(int(main.handle)); sub=U32.GetSubMenu(root,int(top))
    if not sub: raise RuntimeError(f"menu {top} missing")
    cmd=U32.GetMenuItemID(sub,int(child))
    if cmd in (-1,0xFFFFFFFF): raise RuntimeError(f"menu {top}/{child} missing")
    if not U32.PostMessageW(int(main.handle),WM_COMMAND,int(cmd),0):
        raise RuntimeError(f"PostMessage failed {top}/{child}")
    step("invoke",top=top,child=child,command=int(cmd))

def dialogs(app,main):
    out=[]
    for w in wins(app):
        try:
            if w.is_visible() and int(w.handle)!=int(main.handle) and w.class_name()!="TApplication":
                out.append(w)
        except:pass
    return out

def texts(d):
    vals=[]
    try: cs=[d]+d.descendants()
    except: cs=[d]
    for c in cs[:1200]:
        try:
            for t in c.texts():
                s=str(t).strip()
                if s and s not in vals: vals.append(s)
        except:pass
        try:
            s=str(c.window_text()).strip()
            if s and s not in vals: vals.append(s)
        except:pass
    return vals

def wait_dialog(app,main,timeout=20,pred=None):
    end=time.time()+timeout
    while time.time()<end:
        for d in dialogs(app,main):
            if pred is None or pred(d): return d
        time.sleep(.15)
    return None

def click(d,names):
    names={x.casefold() for x in names}
    try:cs=d.descendants()
    except:cs=[]
    for c in cs:
        try:
            if c.class_name() in ("Button","TButton") and c.is_enabled() and c.window_text().strip().casefold() in names:
                c.click();return True
        except:pass
    return False

def set_filename(d,path):
    ed=[]
    for c in d.descendants():
        try:
            if c.class_name().casefold()=="edit" and c.is_visible():ed.append(c)
        except:pass
    if not ed: raise RuntimeError("no file-name Edit")
    ed[-1].set_edit_text(str(path))

def close_dialog(d):
    if click(d,{"ok","&ok","close","&close","cancel","&cancel"}): time.sleep(.4);return
    try:d.close();time.sleep(.4)
    except:pass

try:
    if not SRC.exists(): raise FileNotFoundError(SRC)
    E["source_sha256"]=sha(SRC);E["source_size"]=SRC.stat().st_size
    app=Application(backend="win32").start(f'"{PCB}" "{SRC}"')
    time.sleep(4)
    main=mainwin(app); dismiss_startup(app,main); time.sleep(1)
    step("xml_opened",title=main.window_text(),pid=app.process)
    try: main.capture_as_image().save(OUT/"01_direct_xml_open.png")
    except Exception as e: step("capture_failed",error=repr(e))
    # Save As is File #4 in 5.3.5.1
    invoke(main,0,4)
    dlg=wait_dialog(app,main,20,lambda d:d.class_name()=="#32770")
    if dlg is None: raise RuntimeError("Save As dialog not found")
    step("save_as_dialog",title=dlg.window_text(),texts=texts(dlg)[:80])
    # Explicitly switch Save as type from XML to native binary .dip.
    combos=[]
    try:
        for ctrl in dlg.descendants():
            if ctrl.class_name().casefold()=="combobox" and ctrl.is_visible():
                combos.append(ctrl)
    except: pass
    selected=False
    for cb in combos:
        try:
            vals=[str(x) for x in cb.texts()]
            if any("DipTrace Files (*.dip)" in x for x in vals):
                cb.select("DipTrace Files (*.dip)")
                selected=True
                step("save_type_selected",texts=vals)
                break
        except Exception: pass
    if not selected:
        raise RuntimeError("native DipTrace Files (*.dip) save type not selectable")
    set_filename(dlg,DIP)
    if not click(dlg,{"save","&save","сохранить"}):
        try:dlg.child_window(control_id=1).click()
        except:raise RuntimeError("Save button missing")
    time.sleep(5)
    # Any overwrite/format confirmation
    for d in dialogs(app,main):
        if d.class_name()=="TFProgress":continue
        ts=texts(d);joined=" ".join(ts).casefold()
        step("save_followup",title=d.window_text(),cls=d.class_name(),texts=ts[:80])
        if "error" in joined: raise RuntimeError("save error: "+" | ".join(ts))
        click(d,{"yes","&yes","ok","&ok"})
    time.sleep(2)
    if not DIP.exists():
        cs=list(DIP.parent.glob(DIP.stem+"*"));step("save_candidates",files=[str(x) for x in cs])
        for x in cs:
            if x.suffix.casefold()==".dip":DIP=x;break
    if not DIP.exists(): raise RuntimeError("native .dip not created")
    raw=DIP.read_bytes()
    sig=raw[:16].decode("ascii","replace")
    step("native_saved",size=len(raw),sha256=sha(DIP),signature=sig)
    if len(raw)<10000 or b"DTBOARD" not in raw[:16]: raise RuntimeError("saved file is not non-empty DTBOARD")
    try:main.close()
    except:pass
    time.sleep(2)
    try:
        if app.is_process_running():app.kill()
    except:pass
    # reopen
    app2=Application(backend="win32").start(f'"{PCB}" "{DIP}"')
    time.sleep(4)
    main2=mainwin(app2);dismiss_startup(app2,main2);time.sleep(1)
    step("native_reopened",title=main2.window_text(),pid=app2.process)
    try:main2.capture_as_image().save(OUT/"02_native_reopened.png")
    except Exception as e:step("capture2_failed",error=repr(e))
    try:main2.close()
    except:pass
    time.sleep(2)
    try:
        if app2.is_process_running():app2.kill()
    except:pass
    E["ok"]=True
except Exception as e:
    E["error"]=repr(e);E["traceback"]=traceback.format_exc();print(E["traceback"],flush=True)
finally:
    (OUT/"native_conversion.json").write_text(json.dumps(E,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:E.get(k) for k in ("ok","source_size","source_sha256","error")},ensure_ascii=False,indent=2))
    sys.exit(0 if E.get("ok") else 2)
