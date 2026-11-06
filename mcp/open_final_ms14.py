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
def shot_window(w,name):
    try:
        r=w.rectangle()
        img=pyautogui.screenshot(region=(r.left,r.top,r.width(),r.height()))
        p=out/name; img.save(p); log(f"screenshot {p} rect={r}")
    except Exception as e: log(f"shot error {e}")
try:
    p=subprocess.Popen([str(multisim),str(ms14)])
    log(f"started PID={p.pid} file={ms14}")
    time.sleep(18)
    wins=[]
    for backend in ("win32","uia"):
        try:
            for w in Desktop(backend=backend).windows():
                try:
                    if "Multisim" in w.window_text():
                        wins.append((backend,w.window_text(),w))
                except: pass
        except: pass
    for backend,title,w in wins:
        log(f"window {backend}: {title} rect={w.rectangle()}")
    main=None
    for backend,title,w in wins:
        if backend=="win32" and ("7330744" in title or ".ms14" in title.lower() or "Multisim" in title):
            main=w;break
    if main is None and wins: main=wins[0][2]
    if main is None:
        pyautogui.screenshot(str(out/"no-multisim-window.png"))
        raise RuntimeError("Multisim main window not found")
    try: main.restore()
    except: pass
    try: main.maximize()
    except: pass
    try: main.set_focus()
    except: pass
    time.sleep(4)
    shot_window(main,"01_native_ms14_workspace.png")
    pyautogui.screenshot(str(out/"01_native_ms14_desktop.png"))
    # Dump menu structure for optional zoom-to-fit diagnostics.
    try:
        items=main.menu_items()
        (out/"menu-items.txt").write_text("\n".join(str(x) for x in items),encoding="utf-8")
    except Exception as e: log(f"menu dump error {e}")
    # Try common Multisim View menu fit commands without failing the run.
    for path in ("View->Fit to Page","View->Zoom->Fit to Page","View->Zoom All","View->Zoom->Zoom All"):
        try:
            main.menu_select(path)
            log(f"menu_select success: {path}")
            time.sleep(3)
            shot_window(main,"02_native_ms14_workspace_fit.png")
            break
        except Exception as e:
            log(f"menu_select failed {path}: {e}")
    sys.exit(0)
except Exception:
    log(traceback.format_exc())
    try: pyautogui.screenshot(str(out/"99_exception.png"))
    except: pass
    sys.exit(1)
