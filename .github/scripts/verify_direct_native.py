import ctypes, json, sys, time, traceback, hashlib
from pathlib import Path
from pywinauto.application import Application

PCB=Path(r"C:\Program Files\DipTrace\Pcb.exe")
DIP=Path(sys.argv[1]).resolve()
OUT=Path(sys.argv[2]).resolve()
OUT.mkdir(parents=True,exist_ok=True)
U32=ctypes.windll.user32
WM_COMMAND=0x0111
E={"dip":str(DIP),"steps":[],"ok":False}

def step(name,**kw):
    E["steps"].append({"name":name,**kw}); print(name,kw,flush=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
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
    raise RuntimeError("main not found")
def dismiss_startup(app,main):
    for w in wins(app):
        try:
            if w.is_visible() and int(w.handle)!=int(main.handle) and w.class_name() in ("TForm92","TFMyMessage"):
                ts=gettexts(w);joined=" ".join(ts).casefold()
                if "error" in joined: raise RuntimeError("startup error: "+joined)
                click(w,{"ok","&ok","yes","&yes"}) or w.close()
                time.sleep(.4)
        except RuntimeError:raise
        except:pass
def invoke(main,top,child):
    root=U32.GetMenu(int(main.handle));sub=U32.GetSubMenu(root,int(top))
    cmd=U32.GetMenuItemID(sub,int(child))
    if cmd in (-1,0xFFFFFFFF):raise RuntimeError(f"menu {top}/{child} missing")
    if not U32.PostMessageW(int(main.handle),WM_COMMAND,int(cmd),0):raise RuntimeError("PostMessage failed")
    step("invoke",top=top,child=child,command=int(cmd))
def dialogs(app,main):
    a=[]
    for w in wins(app):
        try:
            if w.is_visible() and int(w.handle)!=int(main.handle) and w.class_name()!="TApplication":a.append(w)
        except:pass
    return a
def gettexts(d):
    vals=[]
    try:cs=[d]+d.descendants()
    except:cs=[d]
    for c in cs[:2000]:
        try:
            for t in c.texts():
                s=str(t).strip()
                if s and s not in vals:vals.append(s)
        except:pass
        try:
            s=c.window_text().strip()
            if s and s not in vals:vals.append(s)
        except:pass
    return vals
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
def close_dialog(d):
    if click(d,{"ok","&ok","close","&close","cancel","&cancel"}):time.sleep(.4);return
    try:d.close();time.sleep(.4)
    except:pass
def wait_final(app,main,timeout=60,kind="drc"):
    end=time.time()+timeout
    while time.time()<end:
        for d in dialogs(app,main):
            try:
                title=d.window_text().strip();cl=d.class_name();ts=gettexts(d)
                if cl=="TFProgress" or "checking" in title.casefold():continue
                joined=" ".join(ts).casefold()
                if kind=="drc":
                    if "drc" in title.casefold() or "error" in title.casefold() or "no errors" in joined or cl=="TFMyMessage":
                        return d,ts
                else:
                    if "connect" in title.casefold() or "no errors" in joined or "error" in joined or cl=="TFMyMessage":
                        return d,ts
            except:pass
        time.sleep(.2)
    return None,[]
def result_ok(title,cl,ts):
    joined=(" ".join(ts)+" "+title).casefold()
    if "no errors" in joined:return True
    if "errors found" in joined or "error found" in joined or "broken" in joined or "unrouted" in joined or "merged" in joined:return False
    # Generic DipTrace success message is TFMyMessage and contains no error tokens.
    return cl=="TFMyMessage" and "error" not in joined

try:
    raw=DIP.read_bytes()
    E["input_size"]=len(raw);E["input_sha256"]=sha(DIP);E["signature"]=raw[:16].decode("ascii","replace")
    if len(raw)<10000 or b"DTBOARD" not in raw[:16]:raise RuntimeError("not a non-empty native DTBOARD")
    app=Application(backend="win32").start(f'"{PCB}" "{DIP}"')
    time.sleep(4)
    main=mainwin(app);dismiss_startup(app,main);time.sleep(1)
    step("opened",title=main.window_text(),pid=app.process)
    try:main.capture_as_image().save(OUT/"03_native_before_checks.png")
    except:pass

    # DRC - Verification #0
    invoke(main,7,0)
    d,ts=wait_final(app,main,60,"drc")
    if d is None:raise RuntimeError("DRC result timeout")
    title=d.window_text();cl=d.class_name()
    drc_ok=result_ok(title,cl,ts)
    step("drc_result",ok=drc_ok,title=title,cls=cl,texts=ts[:500])
    try:d.capture_as_image().save(OUT/"04_drc_result.png")
    except:pass
    close_dialog(d)

    # Connectivity - Verification #4. First dialog is settings, then result.
    invoke(main,7,4)
    settings=None
    end=time.time()+20
    while time.time()<end:
        for x in dialogs(app,main):
            try:
                if "check net connectivity" in x.window_text().casefold():
                    settings=x;break
            except:pass
        if settings:break
        time.sleep(.2)
    if settings is None:raise RuntimeError("connectivity settings timeout")
    step("connectivity_settings",texts=gettexts(settings)[:200])
    try:settings.capture_as_image().save(OUT/"05_connectivity_settings.png")
    except:pass
    # Keep defaults, click OK.
    if not click(settings,{"ok","&ok"}):
        try:settings.child_window(control_id=1).click()
        except:raise RuntimeError("connectivity OK missing")
    d2,ts2=wait_final(app,main,60,"conn")
    if d2 is None:raise RuntimeError("connectivity result timeout")
    title2=d2.window_text();cl2=d2.class_name()
    conn_ok=result_ok(title2,cl2,ts2)
    step("connectivity_result",ok=conn_ok,title=title2,cls=cl2,texts=ts2[:500])
    try:d2.capture_as_image().save(OUT/"06_connectivity_result.png")
    except:pass
    close_dialog(d2)

    # Save native file, close and reopen one final time.
    invoke(main,0,3);time.sleep(2)
    try:main.close()
    except:pass
    time.sleep(2)
    try:
        if app.is_process_running():app.kill()
    except:pass
    app2=Application(backend="win32").start(f'"{PCB}" "{DIP}"')
    time.sleep(4)
    m2=mainwin(app2);dismiss_startup(app2,m2);time.sleep(1)
    step("final_reopen",title=m2.window_text(),pid=app2.process)
    try:m2.capture_as_image().save(OUT/"07_final_reopen.png")
    except:pass
    E["final_size"]=DIP.stat().st_size;E["final_sha256"]=sha(DIP)
    E["drc_ok"]=bool(drc_ok);E["connectivity_ok"]=bool(conn_ok);E["ok"]=bool(drc_ok and conn_ok)
    try:m2.close()
    except:pass
    time.sleep(1)
    try:
        if app2.is_process_running():app2.kill()
    except:pass
except Exception as e:
    E["error"]=repr(e);E["traceback"]=traceback.format_exc();print(E["traceback"],flush=True)
finally:
    (OUT/"native_checks.json").write_text(json.dumps(E,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:E.get(k) for k in ("ok","drc_ok","connectivity_ok","final_size","final_sha256","error")},ensure_ascii=False,indent=2))
    sys.exit(0 if E.get("ok") else 2)
