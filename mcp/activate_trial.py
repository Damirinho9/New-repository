import sys, time, subprocess
from pathlib import Path

multisim = Path(sys.argv[1])

def log(s):
    print(f"[trial] {s}", flush=True)

import pyautogui
from pywinauto import Desktop
pyautogui.FAILSAFE = False

p = subprocess.Popen([str(multisim)])
log(f"started PID={p.pid}")
time.sleep(10)

def trial_present():
    for backend in ("uia","win32"):
        try:
            for w in Desktop(backend=backend).windows():
                for d in w.descendants():
                    try:
                        txt=d.window_text()
                    except Exception:
                        txt=""
                    if txt in ("Begin 7 Day Trial","Log in to Extend Trial"):
                        return True
        except Exception:
            pass
    return False

if trial_present():
    clicked=False
    for backend in ("uia","win32"):
        try:
            for w in Desktop(backend=backend).windows():
                for d in w.descendants():
                    try:
                        txt=d.window_text()
                        rect=d.rectangle()
                    except Exception:
                        continue
                    if txt=="Begin 7 Day Trial" and rect.width()>5 and rect.height()>5:
                        log(f"clicking {txt} at {rect}")
                        d.click_input()
                        clicked=True
                        break
                if clicked:
                    break
        except Exception as e:
            log(f"{backend} scan error: {e}")
        if clicked:
            break
    if not clicked:
        log("using known physical fallback 656,520")
        pyautogui.click(656,520)
    time.sleep(8)

if trial_present():
    log("trial still visible")
    sys.exit(2)

log("trial dialog cleared")
time.sleep(3)
subprocess.run(["taskkill","/IM","Multisim.exe","/T","/F"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
sys.exit(0)
