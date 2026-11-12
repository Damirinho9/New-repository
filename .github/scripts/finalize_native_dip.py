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

CLEARANCE_IDS=[
    67774,67776,67786,67778,67788,67796,
    67780,67790,67798,67804,
    67782,67792,67800,67806,67842,
    67824,67826,67828,67830,67844,67850,
]
BOARD_IDS=[67832,67834,67836,67838,67846,67852]
GENERAL_IN="0.00984"
BOARD_IN="0.01969"

def step(name,**kw):
    rec={"name":name,**kw}; E["steps"].append(rec); print(name,kw,flush=True)

def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()

def wins(app):
    try:return app.windows(visible_only=False,enabled_only=False)
    except:return []

def wait_main(app, timeout=30):
    end=time.time()+timeout
    while time.time()<end:
        for w in wins(app):
            try:
                if w.is_visible() and U32.GetMenu(int(w.handle)) and w.class_name() not in ("#32770","TFMyMessage","TApplication"):
                    return w
            except:pass
        time.sleep(.2)
    raise RuntimeError("main window not found")

def close_startup(app,main):
    for _ in range(5):
        found=False
        for w in wins(app):
            try:
                if w.is_visible() and int(w.handle)!=int(main.handle) and w.class_name()=="TForm92":
                    found=True; w.close(); time.sleep(.5)
            except:pass
        if not found:break

def invoke(main,top,child):
    root=U32.GetMenu(int(main.handle)); sub=U32.GetSubMenu(root,int(top))
    if not sub:raise RuntimeError(f"menu {top} missing")
    cmd=U32.GetMenuItemID(sub,int(child))
    if cmd in (-1,0xFFFFFFFF):raise RuntimeError(f"menu command {top}/{child} missing")
    if not U32.PostMessageW(int(main.handle),WM_COMMAND,int(cmd),0):
        raise RuntimeError(f"PostMessage failed for {top}/{child}")
    step("invoke",top=top,child=child,command=int(cmd))

def controls(d):
    arr=[]
    try:cs=[d]+d.descendants()
    except:cs=[d]
    for c in cs[:1000]:
        rec={}
        for k,fn in [
            ("text",lambda:c.window_text()),("class",lambda:c.class_name()),
            ("id",lambda:c.control_id()),("visible",lambda:c.is_visible()),
            ("enabled",lambda:c.is_enabled())]:
            try:rec[k]=fn()
            except:rec[k]=None
        try:
            r=c.rectangle();rec["rect"]=[r.left,r.top,r.right,r.bottom]
        except:rec["rect"]=None
        try:
            vals=[str(x) for x in c.texts() if str(x).strip()]
            if vals: rec["texts"]=vals[:200]
        except: pass
        arr.append(rec)
    return arr

def visible_dialogs(app,main):
    out=[]
    for w in wins(app):
        try:
            if w.is_visible() and int(w.handle)!=int(main.handle) and w.class_name()!="TApplication":
                out.append(w)
        except:pass
    return out

def wait_dialog(app,main,timeout=15,exclude_titles=()):
    end=time.time()+timeout
    while time.time()<end:
        for d in visible_dialogs(app,main):
            try:
                if d.window_text() not in exclude_titles:return d
            except:pass
        time.sleep(.15)
    return None

def click_named(d,names):
    names={x.casefold() for x in names}
    try:cs=d.descendants()
    except:cs=[]
    for c in cs:
        try:
            if c.class_name() in ("Button","TButton") and c.window_text().strip().casefold() in names and c.is_enabled():
                c.click();return True
        except:pass
    return False

def set_edit(d,cid,val):
    c=d.child_window(control_id=cid)
    c.set_edit_text(val)
    got=c.window_text().strip()
    if got!=val:raise RuntimeError(f"edit {cid} expected {val} got {got}")
    step("set_rule",id=cid,value=val)

def checkbox_set(d,cid,want=True):
    c=d.child_window(control_id=cid)
    try:state=int(c.get_check_state())
    except:state=0
    if bool(state)!=bool(want):c.click()
    step("checkbox",id=cid,want=bool(want))

def close_dialog(d):
    if click_named(d,{"close","ok","cancel","закрыть","ок","отмена"}):time.sleep(.4);return
    try:d.close();time.sleep(.4)
    except:pass

def save_native(main):
    invoke(main,0,3)
    time.sleep(1)
    step("saved",sha256=sha(DIP),size=DIP.stat().st_size)

def apply_rules(app,main):
    invoke(main,7,1)
    d=wait_dialog(app,main,10)
    if not d or "design rules" not in d.window_text().casefold():
        raise RuntimeError(f"Design Rules dialog not found: {[x.window_text() for x in visible_dialogs(app,main)]}")
    step("design_rules_open",controls=controls(d))

    # DipTrace regenerates Win32 control IDs between builds/processes. The
    # clearance matrix geometry is stable, so identify enabled numeric fields
    # by their row coordinates instead of fragile IDs.
    changed=[]
    try:
        desc=d.descendants()
    except Exception:
        desc=[]
    for ctrl in desc:
        try:
            if ctrl.class_name()!="TEdit" or not ctrl.is_visible() or not ctrl.is_enabled():
                continue
            r=ctrl.rectangle()
            cy=(r.top+r.bottom)/2
            # Matrix rows: Trace/Via/Pad/SMD/Copper/Drill ~= 280..400 px.
            # Board row ~= 424 px. Same-net fields start around 483 px.
            if 260 <= cy <= 410:
                val=GENERAL_IN
            elif 410 < cy <= 445:
                val=BOARD_IN
            else:
                continue
            before=ctrl.window_text().strip()
            ctrl.set_edit_text(val)
            after=ctrl.window_text().strip()
            if after!=val:
                raise RuntimeError(f"rule field at {list(r)} expected {val} got {after}")
            changed.append({"rect":[r.left,r.top,r.right,r.bottom],"before":before,"after":after})
        except Exception as exc:
            if isinstance(exc, RuntimeError):
                raise
    if len(changed) < 20:
        raise RuntimeError(f"too few clearance fields changed: {len(changed)}")
    step("rules_changed",count=len(changed),fields=changed,
         general_in=GENERAL_IN,board_in=BOARD_IN,
         general_mm=0.249936,board_mm=0.500126)

    d.capture_as_image().save(OUT/"01_rules_set.png")
    if not click_named(d,{"ok","&ok","ок"}):
        raise RuntimeError("Design Rules OK button not found")
    time.sleep(1)
    save_native(main)

def run_drc(app,main,label):
    invoke(main,7,0)
    end=time.time()+45
    d=None
    while time.time()<end:
        ds=visible_dialogs(app,main)
        # DRC shows TFProgress while calculating. Never close/interpret it.
        finals=[]
        for cand in ds:
            try:
                title=cand.window_text().strip()
                cls=cand.class_name()
                if cls=="TFProgress" or "progress" in title.casefold():
                    continue
                if "drc" in title.casefold() or cls=="TFMyMessage" or "error" in title.casefold():
                    finals.append(cand)
            except: pass
        if finals:
            d=finals[0]; break
        time.sleep(.2)
    if d is None:
        raise RuntimeError("DRC final result dialog did not appear")
    title=d.window_text(); cs=controls(d)
    texts=[]
    for x in cs:
        if x.get("text"): texts.append(str(x["text"]))
        texts.extend([str(v) for v in x.get("texts",[]) if str(v).strip()])
    step(label+"_drc",title=title,cls=d.class_name(),texts=texts,controls=cs)
    try:d.capture_as_image().save(OUT/f"{label}_drc.png")
    except:pass
    joined=" ".join(texts).casefold()
    ok=("no errors" in joined) or ("no errors" in title.casefold())
    if not ok and d.class_name()=="TFMyMessage":
        ok=("error" not in joined and "violation" not in joined)
    close_dialog(d)
    return ok,title,texts

def run_connectivity(app,main,label):
    invoke(main,7,4)
    d=wait_dialog(app,main,10)
    if d is None or "check net connectivity" not in d.window_text().casefold():
        raise RuntimeError(f"Connectivity settings missing: {None if d is None else d.window_text()}")
    step(label+"_connectivity_settings",controls=controls(d))
    # Defaults are all checked; force all TCheckBox controls checked.
    try:
        for c in d.descendants():
            if c.class_name()=="TCheckBox" and c.is_enabled():
                try:
                    if int(c.get_check_state())==0:c.click()
                except:pass
    except:pass
    d.capture_as_image().save(OUT/f"{label}_connectivity_settings.png")
    if not click_named(d,{"ok","&ok","ок"}):raise RuntimeError("Connectivity OK button missing")
    time.sleep(.5)
    # Clean check normally yields a small "No Errors" message.
    result=wait_dialog(app,main,15)
    if result is None:
        step(label+"_connectivity",title="",cls="",texts=[],note="no result dialog")
        return False,"",[]
    title=result.window_text(); cs=controls(result)
    texts=[str(x.get("text") or "") for x in cs if x.get("text")]
    step(label+"_connectivity",title=title,cls=result.class_name(),texts=texts,controls=cs)
    try:result.capture_as_image().save(OUT/f"{label}_connectivity_result.png")
    except:pass
    joined=" ".join(texts).casefold()
    ok=("no errors" in joined) or ("no errors" in title.casefold())
    if not ok and result.class_name()=="TFMyMessage":
        # Treat generic message as pass only if it does not mention an error.
        ok=("error" not in joined and "broken" not in joined and "unrouted" not in joined)
    close_dialog(result)
    return ok,title,texts

def open_native():
    app=Application(backend="win32").start(f'"{PCB}" "{DIP}"')
    time.sleep(3)
    m=wait_main(app);close_startup(app,m);time.sleep(.8)
    step("opened",title=m.window_text(),pid=app.process)
    return app,m

def close_app(app,main):
    try:main.close()
    except:pass
    time.sleep(1.5)
    try:
        if app.is_process_running():app.kill()
    except:pass

try:
    raw=DIP.read_bytes()
    if len(raw)<10000 or b"DTBOARD" not in raw[:16]:raise RuntimeError("input is not a non-empty native DTBOARD")
    E["input_sha256"]=sha(DIP);E["input_size"]=len(raw)
    app,main=open_native()
    apply_rules(app,main)
    pre_drc=run_drc(app,main,"before_reopen")
    pre_conn=run_connectivity(app,main,"before_reopen")
    save_native(main)
    close_app(app,main)

    # Reopen saved native file and repeat both native checks.
    app2,main2=open_native()
    main2.capture_as_image().save(OUT/"02_reopened_native.png")
    drc_ok,drc_title,drc_texts=run_drc(app2,main2,"after_reopen")
    conn_ok,conn_title,conn_texts=run_connectivity(app2,main2,"after_reopen")
    save_native(main2)
    E["final_sha256"]=sha(DIP);E["final_size"]=DIP.stat().st_size
    E["drc_ok"]=bool(drc_ok);E["connectivity_ok"]=bool(conn_ok)
    E["drc_title"]=drc_title;E["connectivity_title"]=conn_title
    E["ok"]=bool(drc_ok and conn_ok and E["final_size"]>10000)
    close_app(app2,main2)
except Exception as e:
    E["error"]=repr(e);E["traceback"]=traceback.format_exc()
finally:
    (OUT/"final_native_evidence.json").write_text(json.dumps(E,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:E.get(k) for k in ["ok","drc_ok","connectivity_ok","final_size","final_sha256","error"]},ensure_ascii=False,indent=2))
    sys.exit(0 if E.get("ok") else 2)
