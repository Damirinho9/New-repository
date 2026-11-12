import os, sys, time, json, re, hashlib, traceback
from pathlib import Path
from pywinauto.application import Application

PCB_EXE = Path(r"C:\Program Files\DipTrace\Pcb.exe")
BOARD = Path(os.environ["BOARD_PATH"]).resolve()
OUTDIR = Path(os.environ["OUTDIR"]).resolve()
OUTDIR.mkdir(parents=True, exist_ok=True)
TARGET = OUTDIR / "7313294_variant12_NATIVE.dip"
LOG = OUTDIR / "nativeize.log"
E = {"board": str(BOARD), "target": str(TARGET), "steps": [], "menus": [], "windows": []}

def log(s):
    s=str(s)
    safe=s.encode("ascii","backslashreplace").decode("ascii")
    print(safe, flush=True)
    with LOG.open("a", encoding="utf-8") as f: f.write(s+"\n")
    E["steps"].append(s)

def norm(s): return re.sub(r"[^a-z0-9]+","",str(s).replace("&","").casefold())

def sha256(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def save_evidence():
    (OUTDIR/"evidence.json").write_text(json.dumps(E,ensure_ascii=False,indent=2),encoding="utf-8")

def wait_main(app, timeout=30):
    end=time.time()+timeout
    last=[]
    while time.time()<end:
        last=[]
        try: wins=app.windows(visible_only=False,enabled_only=True)
        except Exception: wins=[]
        for w in wins:
            try:
                last.append((w.window_text(),w.class_name()))
                if w.menu() is not None and w.class_name() not in ("#32770","TFMyMessage"):
                    return w
            except Exception: pass
        time.sleep(.25)
    raise RuntimeError("main window not found: "+repr(last))

def walk(menu,prefix=()):
    out=[]
    try: items=menu.items()
    except Exception: return out
    for it in items:
        try: txt=it.text()
        except Exception: txt=""
        path=prefix+(txt,)
        out.append((path,it))
        try: sm=it.sub_menu()
        except Exception: sm=None
        if sm is not None: out.extend(walk(sm,path))
    return out

def dump_menu(win,label):
    arr=[" -> ".join(p) for p,_ in walk(win.menu())]
    E["menus"].append({"label":label,"items":arr})
    log(label+" menus:\n  "+"\n  ".join(arr))
    return arr

def all_windows(app):
    out=[]
    try: wins=app.windows(visible_only=False,enabled_only=False)
    except Exception: return out
    for w in wins:
        try: out.append((w,w.window_text(),w.class_name(),w.is_visible(),w.is_enabled()))
        except Exception: pass
    return out

def dump_windows(app,label):
    data=[]
    for w,t,c,v,en in all_windows(app):
        children=[]
        try:
            for ch in w.children():
                try:
                    children.append({"text":ch.window_text(),"class":ch.class_name(),"id":ch.control_id(),"enabled":ch.is_enabled()})
                except Exception: pass
        except Exception: pass
        data.append({"title":t,"class":c,"visible":v,"enabled":en,"children":children[:100]})
    E["windows"].append({"label":label,"data":data})
    log(label+" windows="+json.dumps(data,ensure_ascii=False))

def screenshot(win,name):
    try:
        win.capture_as_image().save(OUTDIR/name)
        log("screenshot "+name)
    except Exception as x: log("screenshot failed "+repr(x))

def find_menu(win, want):
    candidates=[]
    for path,it in walk(win.menu()):
        full=" ".join(norm(x) for x in path)
        if want(full,path):
            candidates.append((path,it))
    candidates.sort(key=lambda z:(len(z[0]),len(" ".join(z[0]))), reverse=True)
    return candidates[0] if candidates else None

def invoke(win,path,it):
    log("menu invoke: "+" -> ".join(path))
    try: it.click()
    except Exception: win.menu_item("->".join(path)).click()

def wait_dialog(app, main_handle, timeout=15):
    end=time.time()+timeout
    while time.time()<end:
        for w,t,c,v,en in all_windows(app):
            if int(w.handle)==int(main_handle) or not v: continue
            if c in ("#32770","TFMyMessage","TForm60","TForm1","TForm2","TForm3","TForm4","TForm5"):
                return w
        time.sleep(.2)
    return None

def click_button(dlg, wanted=("ok","import","open","save","yes","check","run","rundrc","start")):
    cand=[]
    for ch in dlg.children():
        try:
            if ch.class_name() not in ("Button","TButton") or not ch.is_enabled(): continue
            n=norm(ch.window_text()); cid=ch.control_id(); score=0
            if cid==1: score+=100
            if n in wanted: score+=80
            if any(x in n for x in wanted): score+=30
            if n in ("cancel","no","close"): score-=150
            cand.append((score,ch,n,cid))
        except Exception: pass
    cand.sort(key=lambda x:x[0], reverse=True)
    if not cand or cand[0][0]<=0: return False
    score,ch,n,cid=cand[0]
    log("dialog button "+repr(n)+" id="+str(cid))
    try: ch.click()
    except Exception: ch.click_input()
    return True

def common_filename(dlg,path):
    edit=None
    children=dlg.children()
    for ch in children:
        try:
            if ch.class_name()=="Edit" and ch.control_id()==1148: edit=ch; break
        except Exception: pass
    if edit is None:
        edits=[]
        for ch in children:
            try:
                if ch.class_name()=="Edit": edits.append(ch)
            except Exception: pass
        if edits: edit=edits[-1]
    if edit is None: raise RuntimeError("filename edit not found")
    edit.set_edit_text(str(path))
    if not click_button(dlg,("open","save","ok","import")):
        raise RuntimeError("dialog action button not found")

def handle_modal_defaults(app,main,seconds=12):
    end=time.time()+seconds
    while time.time()<end:
        did=False
        for w,t,c,v,en in all_windows(app):
            if not v or int(w.handle)==int(main.handle): continue
            if c=="#32770": continue
            dump_windows(app,"modal:"+t)
            if click_button(w):
                did=True; time.sleep(.8); break
        if not did: time.sleep(.3)

def wait_file(p,timeout=30):
    end=time.time()+timeout; prev=-1
    while time.time()<end:
        if p.exists() and p.stat().st_size>0:
            s=p.stat().st_size
            if s==prev:
                time.sleep(.8)
                if p.stat().st_size==s:return s
            prev=s
        time.sleep(.3)
    raise RuntimeError("file not created "+str(p))

def verify(app,main,kind):
    def pred(full,path):
        if kind=="drc":
            return ("designrules" in full or "checkdesignrules" in full or ("drc" in full and "verif" in full))
        return ("connectivity" in full or "checknet" in full)
    m=find_menu(main,pred)
    if not m: raise RuntimeError("verification menu not found: "+kind)
    invoke(main,*m)
    time.sleep(1)
    dump_windows(app,kind+" after invoke")
    for _ in range(6):
        dlg=wait_dialog(app,main.handle,2)
        if dlg is None: break
        if not click_button(dlg,("run","rundrc","check","ok","start")): break
        time.sleep(1)
    dump_windows(app,kind+" result")
    screenshot(main,kind+"_main.png")

def run():
    if not PCB_EXE.exists(): raise RuntimeError("Pcb.exe absent")
    log("input sha256="+sha256(BOARD))
    app=Application(backend="win32").start(cmd_line='"'+str(PCB_EXE)+'"')
    main=wait_main(app)
    screenshot(main,"00_blank.png"); dump_menu(main,"blank")

    m=find_menu(main,lambda full,path: "import" in full and "kicad" in full)
    if not m: raise RuntimeError("KiCad import menu absent")
    invoke(main,*m)
    dlg=wait_dialog(app,main.handle,12)
    if dlg is None: raise RuntimeError("KiCad file dialog absent")
    dump_windows(app,"kicad file dialog")
    common_filename(dlg,BOARD)
    time.sleep(1)
    handle_modal_defaults(app,main,12)
    time.sleep(3)
    main=wait_main(app)
    screenshot(main,"01_imported.png"); dump_menu(main,"imported")
    log("imported title="+main.window_text())

    m=find_menu(main,lambda full,path: len(path)>=2 and "file" in norm(path[0]) and "saveas" in full)
    if m: invoke(main,*m)
    else:
        log("Save As menu text not found; Ctrl+Shift+S")
        main.type_keys("^+s")
    dlg=wait_dialog(app,main.handle,10)
    if dlg is None: raise RuntimeError("Save As dialog absent")
    dump_windows(app,"save as dialog")
    common_filename(dlg,TARGET)
    time.sleep(2)
    handle_modal_defaults(app,main,6)
    size=wait_file(TARGET,30)
    E["native_size"]=size; E["native_sha256"]=sha256(TARGET)
    log("native created size="+str(size)+" sha256="+E["native_sha256"])
    screenshot(main,"02_saved.png")
    save_evidence()

    try: main.close()
    except Exception: pass
    time.sleep(2)
    try:
        if app.is_process_running(): app.kill()
    except Exception: pass

    app2=Application(backend="win32").start(cmd_line='"'+str(PCB_EXE)+'" "'+str(TARGET)+'"')
    main2=wait_main(app2,30)
    E["reopen_title"]=main2.window_text()
    log("reopened="+main2.window_text())
    screenshot(main2,"03_reopened.png"); dump_menu(main2,"reopened")
    verify(app2,main2,"drc")
    verify(app2,main2,"connectivity")
    try: main2.type_keys("^s")
    except Exception: pass
    time.sleep(2)
    E["after_checks_sha256"]=sha256(TARGET)
    E["after_checks_size"]=TARGET.stat().st_size
    screenshot(main2,"04_final.png")
    save_evidence()
    log("SUCCESS")
    try: main2.close()
    except Exception: pass

if __name__=="__main__":
    try:
        run()
    except Exception as x:
        E["error"]=repr(x); E["traceback"]=traceback.format_exc()
        log("ERROR "+repr(x)); log(E["traceback"])
        try: save_evidence()
        except Exception: pass
        sys.exit(1)
