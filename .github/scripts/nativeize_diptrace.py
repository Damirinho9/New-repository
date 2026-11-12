import os, sys, time, json, re, hashlib, traceback, ctypes
from pathlib import Path
from pywinauto.application import Application

PCB_EXE = Path(r"C:\Program Files\DipTrace\Pcb.exe")
BOARD = Path(os.environ["BOARD_PATH"]).resolve()
OUTDIR = Path(os.environ["OUTDIR"]).resolve()
OUTDIR.mkdir(parents=True, exist_ok=True)
TARGET = OUTDIR / "7313294_variant12_NATIVE.dip"
LOG = OUTDIR / "nativeize.log"
E = {"board": str(BOARD), "target": str(TARGET), "steps": [], "menus": [], "windows": []}
U32 = ctypes.windll.user32
MF_BYPOSITION = 0x00000400
WM_COMMAND = 0x0111

def clean_for_io(s):
    return str(s).encode("utf-8","backslashreplace").decode("utf-8")

def log(s):
    s=clean_for_io(s)
    print(s.encode("ascii","backslashreplace").decode("ascii"), flush=True)
    with LOG.open("a", encoding="utf-8", errors="backslashreplace") as fh: fh.write(s+"\n")
    E["steps"].append(s)

def norm(s):
    s=clean_for_io(s).replace("&","").casefold()
    return re.sub(r"[^a-zа-яё0-9]+","",s)

def sha256(p):
    h=hashlib.sha256()
    with open(p,"rb") as fh:
        for b in iter(lambda:fh.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def save_evidence():
    (OUTDIR/"evidence.json").write_text(json.dumps(E,ensure_ascii=True,indent=2),encoding="utf-8")

def wait_main(app, timeout=30):
    end=time.time()+timeout
    last=[]
    while time.time()<end:
        last=[]
        try: wins=app.windows(visible_only=False,enabled_only=True)
        except Exception: wins=[]
        for w in wins:
            try:
                last.append((clean_for_io(w.window_text()),w.class_name(),int(w.handle)))
                if U32.GetMenu(int(w.handle)) and w.class_name() not in ("#32770","TFMyMessage"):
                    return w
            except Exception: pass
        time.sleep(.25)
    raise RuntimeError("main DipTrace window not found: "+repr(last))

def menu_tree(hwnd):
    root=U32.GetMenu(int(hwnd))
    if not root: return []
    out=[]
    def rec(hmenu, idxpath=(), textpath=()):
        count=U32.GetMenuItemCount(hmenu)
        for pos in range(max(0,count)):
            buf=ctypes.create_unicode_buffer(1024)
            U32.GetMenuStringW(hmenu,pos,buf,1024,MF_BYPOSITION)
            text=clean_for_io(buf.value)
            sub=U32.GetSubMenu(hmenu,pos)
            cid=U32.GetMenuItemID(hmenu,pos)
            recd={"indices":list(idxpath+(pos,)),"texts":list(textpath+(text,)),"id":int(cid) if cid != 0xFFFFFFFF else -1}
            out.append(recd)
            if sub: rec(sub,idxpath+(pos,),textpath+(text,))
    rec(root)
    return out

def dump_menu(win,label):
    arr=menu_tree(win.handle)
    E["menus"].append({"label":label,"items":arr})
    for x in arr:
        log(label+" menu "+"/".join("#"+str(i) for i in x["indices"])+" id="+str(x["id"])+" text="+" -> ".join(x["texts"]))
    return arr

def find_menu(win, predicate):
    arr=menu_tree(win.handle)
    candidates=[]
    for x in arr:
        full=" ".join(norm(t) for t in x["texts"])
        if x["id"]>=0 and predicate(full,x):
            candidates.append(x)
    candidates.sort(key=lambda x:(len(x["indices"]),len(" ".join(x["texts"]))),reverse=True)
    return candidates[0] if candidates else None

def invoke(win,item):
    if not item or item["id"]<0: raise RuntimeError("invalid menu item")
    log("invoke id="+str(item["id"])+" path="+"/".join("#"+str(i) for i in item["indices"])+" text="+" -> ".join(item["texts"]))
    if not U32.PostMessageW(int(win.handle),WM_COMMAND,int(item["id"]),0):
        raise RuntimeError("PostMessageW WM_COMMAND failed")

def all_windows(app):
    out=[]
    try: wins=app.windows(visible_only=False,enabled_only=False)
    except Exception: return out
    for w in wins:
        try: out.append((w,clean_for_io(w.window_text()),w.class_name(),w.is_visible(),w.is_enabled()))
        except Exception: pass
    return out

def dump_windows(app,label):
    data=[]
    for w,t,c,v,en in all_windows(app):
        children=[]
        try:
            for ch in w.children():
                try:
                    children.append({"text":clean_for_io(ch.window_text()),"class":ch.class_name(),"id":ch.control_id(),"enabled":ch.is_enabled()})
                except Exception: pass
        except Exception: pass
        data.append({"title":t,"class":c,"visible":v,"enabled":en,"children":children[:120]})
    E["windows"].append({"label":label,"data":data})
    log(label+" windows="+json.dumps(data,ensure_ascii=True))

def focus(win):
    try: win.set_focus()
    except Exception: pass
    try: win.maximize()
    except Exception: pass
    time.sleep(.4)

def screenshot(win,name):
    try:
        focus(win)
        win.capture_as_image().save(OUTDIR/name)
        log("screenshot "+name)
    except Exception as exc: log("screenshot failed "+repr(exc))

def is_common_file_dialog(w):
    try:
        if w.class_name()!="#32770": return False
        for ch in w.children():
            try:
                if ch.class_name()=="Edit" and ch.control_id()==1148: return True
            except Exception: pass
    except Exception: pass
    return False

def wait_common_file_dialog(app,main_handle,timeout=15):
    end=time.time()+timeout
    while time.time()<end:
        for w,t,c,v,en in all_windows(app):
            if v and int(w.handle)!=int(main_handle) and is_common_file_dialog(w): return w
        time.sleep(.2)
    return None

def click_button(dlg,wanted=("ok","import","open","save","yes","check","run","rundrc","start","готово","импорт","открыть","сохранить","да","проверить","запуск")):
    cand=[]
    for ch in dlg.children():
        try:
            if ch.class_name() not in ("Button","TButton") or not ch.is_enabled(): continue
            n=norm(ch.window_text()); cid=ch.control_id(); score=0
            if cid==1: score+=100
            if n in wanted: score+=80
            if any(norm(x) in n for x in wanted): score+=30
            if n in ("cancel","no","close","отмена","нет","закрыть"): score-=150
            cand.append((score,ch,n,cid))
        except Exception: pass
    cand.sort(key=lambda x:x[0],reverse=True)
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
    if edit is None: raise RuntimeError("common filename edit 1148 not found")
    edit.set_edit_text(str(path))
    if not click_button(dlg,("open","save","ok","import","открыть","сохранить","импорт")):
        raise RuntimeError("common file dialog action button not found")

def handle_modal_defaults(app,main,seconds=15):
    end=time.time()+seconds
    seen=set()
    while time.time()<end:
        did=False
        for w,t,c,v,en in all_windows(app):
            if not v or int(w.handle)==int(main.handle) or is_common_file_dialog(w): continue
            key=(int(w.handle),t,c)
            if key not in seen:
                seen.add(key); dump_windows(app,"modal:"+t)
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
    if kind=="drc":
        pred=lambda full,x: ("designrules" in full or "drc" in full or ("правил" in full and ("провер" in full or "контрол" in full)))
    else:
        pred=lambda full,x: ("connectivity" in full or "checknet" in full or ("соедин" in full and ("провер" in full or "контрол" in full)) or ("связ" in full and "провер" in full))
    m=find_menu(main,pred)
    if not m:
        # Verification menu is top-level #7. In current PCB Layout:
        # #7/#0 = Check Design Rules, #7/#1 = Check Net Connectivity.
        wanted=[7,0] if kind=="drc" else [7,1]
        arr=menu_tree(main.handle)
        m=next((x for x in arr if x["indices"]==wanted and x["id"]>=0),None)
    if not m:
        dump_menu(main,"verification-search-"+kind)
        raise RuntimeError("verification menu not found: "+kind)
    invoke(main,m)
    time.sleep(1)
    dump_windows(app,kind+" after invoke")
    handle_modal_defaults(app,main,8)
    dump_windows(app,kind+" result")
    screenshot(main,kind+"_main.png")


def dismiss_getting_started(app, main):
    for _ in range(5):
        found=False
        for w,t,cl,v,en in all_windows(app):
            if v and cl=="TForm92" and ("gettingstarted" in norm(t) or t=="Getting Started"):
                found=True
                log("closing Getting Started")
                try: w.close()
                except Exception:
                    try:
                        w.set_focus(); w.type_keys("%{F4}")
                    except Exception: pass
                time.sleep(.8)
        if not found: break
    # Wait until main is enabled again.
    end=time.time()+5
    while time.time()<end:
        try:
            if main.is_enabled(): return
        except Exception: pass
        time.sleep(.2)

def get_file_type_text(dlg):
    for ch in dlg.children():
        try:
            if ch.class_name()=="ComboBox" and ch.control_id()==1136:
                return clean_for_io(ch.window_text())
        except Exception: pass
    return ""

def cancel_dialog(dlg):
    for ch in dlg.children():
        try:
            if ch.class_name() in ("Button","TButton") and ch.control_id()==2:
                ch.click(); return
        except Exception: pass
    try: dlg.close()
    except Exception: pass

def close_nonmain_visible(app, main):
    for w,t,cl,v,en in all_windows(app):
        if not v or int(w.handle)==int(main.handle): continue
        if cl in ("#32770","TForm92","TFMyMessage") or cl.startswith("T"):
            log("closing probe window title="+t+" class="+cl)
            try: w.close()
            except Exception:
                try: w.set_focus(); w.type_keys("%{F4}")
                except Exception: pass
            time.sleep(.4)

def discover_kicad_import(app, main):
    arr=menu_tree(main.handle)
    probe=[]
    # File -> Import is #0/#8 in this DipTrace build.
    for pos in range(0,20):
        item=next((x for x in arr if x["indices"]==[0,8,pos] and x["id"]>=0),None)
        if not item: continue
        invoke(main,item)
        time.sleep(.8)
        dlg=wait_common_file_dialog(app,main.handle,2.0)
        if dlg is not None:
            ftype=get_file_type_text(dlg)
            rec={"pos":pos,"id":item["id"],"file_type":ftype}
            probe.append(rec); log("import probe "+json.dumps(rec,ensure_ascii=True))
            cancel_dialog(dlg); time.sleep(.5)
            if "kicad" in norm(ftype) or "kicadpcb" in norm(ftype):
                E["kicad_import_probe"]=probe
                log("KiCad importer discovered at #0/#8/#"+str(pos)+" id="+str(item["id"])+" type="+ftype)
                return item
        else:
            # Custom import form. Record and close it, then continue.
            vis=[]
            for w,t,cl,v,en in all_windows(app):
                if v and int(w.handle)!=int(main.handle):
                    vis.append({"title":t,"class":cl})
            rec={"pos":pos,"id":item["id"],"custom_windows":vis}
            probe.append(rec); log("import probe "+json.dumps(rec,ensure_ascii=True))
            close_nonmain_visible(app,main)
            time.sleep(.5)
    E["kicad_import_probe"]=probe
    raise RuntimeError("Could not discover KiCad importer from File->Import filters")

def assert_native_nonempty(path):
    size=path.stat().st_size
    with open(path,"rb") as fh: sig=fh.read(8)
    log("native signature="+repr(sig)+" size="+str(size))
    if b"DTBOARD" not in sig:
        raise RuntimeError("Saved file does not have DTBOARD signature")
    if size < 10000:
        raise RuntimeError("Native .dip is suspiciously small / likely blank: "+str(size))

def run():
    if not PCB_EXE.exists(): raise RuntimeError("Pcb.exe absent")
    log("input sha256="+sha256(BOARD))
    app=Application(backend="win32").start(cmd_line='"'+str(PCB_EXE)+'"')
    main=wait_main(app)
    dismiss_getting_started(app,main)
    focus(main)
    screenshot(main,"00_blank.png")
    dump_menu(main,"blank")

    # Discover the actual KiCad item from its Windows file-dialog filter.
    # This is robust to new importers shifting menu indices between DipTrace releases.
    m=discover_kicad_import(app,main)
    invoke(main,m)
    dlg=wait_common_file_dialog(app,main.handle,12)
    if dlg is None:
        dump_windows(app,"no kicad file dialog")
        raise RuntimeError("KiCad common file dialog absent")
    dump_windows(app,"kicad file dialog")
    common_filename(dlg,BOARD)
    time.sleep(1)
    handle_modal_defaults(app,main,15)
    time.sleep(3)
    main=wait_main(app)
    screenshot(main,"01_imported.png")
    dump_menu(main,"imported")
    log("imported title="+clean_for_io(main.window_text()))

    m=find_menu(main,lambda full,x: ("saveas" in full or "сохранитькак" in full))
    if m: invoke(main,m)
    else:
        log("Save As menu not found by text, using #0->#5/#0->#4 fallback")
        # Known DipTrace menu positions vary by release; first find leaf near Save by index.
        arr=menu_tree(main.handle)
        fallback=next((x for x in arr if x["indices"] in ([0,5],[0,4]) and x["id"]>=0),None)
        if fallback: invoke(main,fallback)
        else: main.type_keys("^+s")
    dlg=wait_common_file_dialog(app,main.handle,10)
    if dlg is None:
        dump_windows(app,"no save as dialog")
        raise RuntimeError("Save As common dialog absent")
    dump_windows(app,"save as dialog")
    common_filename(dlg,TARGET)
    time.sleep(2)
    handle_modal_defaults(app,main,8)
    size=wait_file(TARGET,30)
    assert_native_nonempty(TARGET)
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
    dismiss_getting_started(app2,main2)
    focus(main2)
    E["reopen_title"]=clean_for_io(main2.window_text())
    log("reopened="+E["reopen_title"])
    screenshot(main2,"03_reopened.png")
    dump_menu(main2,"reopened")
    verify(app2,main2,"drc")
    verify(app2,main2,"connectivity")
    try:
        m=find_menu(main2,lambda full,x: ("save" in full or "сохранить" in full) and not ("saveas" in full or "сохранитькак" in full))
        if m: invoke(main2,m)
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
    except Exception as exc:
        E["error"]=repr(exc); E["traceback"]=traceback.format_exc()
        log("ERROR "+repr(exc)); log(E["traceback"])
        try: save_evidence()
        except Exception as e2: log("evidence save failed "+repr(e2))
        sys.exit(1)
