import sys,time,subprocess,traceback
from pathlib import Path
import pyautogui
from pywinauto import Desktop

multisim=Path(sys.argv[1]); ms14=Path(sys.argv[2]); out=Path(sys.argv[3])
out.mkdir(parents=True,exist_ok=True)
logf=out/"open-final.log"
def log(s):
    print(s,flush=True)
    with logf.open("a",encoding="utf-8") as f:f.write(s+"\n")
def desktop_shot(name):
    p=out/name; pyautogui.screenshot(str(p)); log(f"desktop screenshot {p}")
def shot_window(w,name):
    try:
        r=w.rectangle()
        img=pyautogui.screenshot(region=(r.left,r.top,r.width(),r.height()))
        p=out/name; img.save(p); log(f"window screenshot {p} rect={r}")
    except Exception as e: log(f"shot error {e}")
def buttons():
    result=[]
    for backend in ("uia","win32"):
        try:
            for w in Desktop(backend=backend).windows():
                for d in w.descendants():
                    try:
                        txt=d.window_text().strip()
                        cls=d.class_name()
                        rect=d.rectangle()
                    except Exception:
                        continue
                    if txt and ("button" in cls.lower() or backend=="uia"):
                        result.append((backend,txt,d,rect))
        except Exception:
            pass
    return result
def click_named(names):
    for backend,txt,d,rect in buttons():
        if txt in names and rect.width()>5 and rect.height()>5:
            try:
                log(f"click {txt!r} backend={backend} rect={rect}")
                d.click_input()
                return txt
            except Exception as e:
                log(f"click failed {txt}: {e}")
    return None
def find_main():
    cand=[]
    for backend in ("win32","uia"):
        try:
            for w in Desktop(backend=backend).windows():
                try:
                    title=w.window_text()
                    if "Multisim" in title:
                        cand.append((backend,title,w))
                except: pass
        except: pass
    for backend,title,w in cand:
        if "7330744" in title or "PhotoRelay" in title:
            return w,cand
    for backend,title,w in cand:
        if title.strip() not in ("Multisim",""):
            return w,cand
    return (cand[0][2] if cand else None),cand

try:
    p=subprocess.Popen([str(multisim),str(ms14)])
    log(f"started PID={p.pid} file={ms14}")
    time.sleep(16)
    desktop_shot("00_after_launch.png")

    # Trial has already been started in a previous launch of this runner.
    # Multisim then shows a reminder modal. Dismiss it before evaluating workspace.
    clicked=click_named({"Remind Me Later"})
    if clicked:
        log("trial reminder dismissed")
        time.sleep(8)
    else:
        # Fallback for slightly different NI wording.
        clicked=click_named({"Cancel","OK","Continue"})
        if clicked:
            log(f"dismissed modal with {clicked}")
            time.sleep(6)

    desktop_shot("01_after_license_reminder.png")
    main,cand=find_main()
    for backend,title,w in cand:
        try: log(f"window {backend}: {title!r} rect={w.rectangle()}")
        except: pass
    if main is None:
        raise RuntimeError("Multisim workspace window not found after dismissing trial reminder")
    try: main.restore()
    except: pass
    try: main.maximize()
    except: pass
    try: main.set_focus()
    except: pass
    time.sleep(5)
    shot_window(main,"02_native_ms14_workspace.png")
    desktop_shot("02_native_ms14_desktop.png")

    # Try menu keyboard access for "View" and common zoom-all shortcuts,
    # but retain the unmodified first workspace screenshot as evidence.
    try:
        pyautogui.hotkey("alt","v")
        time.sleep(1)
        desktop_shot("03_view_menu.png")
        pyautogui.press("esc")
    except: pass

    # Confirm the design filename is present somewhere in the window inventory.
    titles=[title for _,title,_ in cand]
    (out/"window-titles.txt").write_text("\n".join(titles),encoding="utf-8")
    if not any(("7330744" in x or "PhotoRelay" in x) for x in titles):
        log("warning: filename not visible in title, but Multisim workspace is open")
    sys.exit(0)
except Exception:
    log(traceback.format_exc())
    try: desktop_shot("99_exception.png")
    except: pass
    sys.exit(1)
