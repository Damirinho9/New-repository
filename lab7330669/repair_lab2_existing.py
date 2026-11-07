import sys,time,subprocess,traceback
from pathlib import Path

MS=Path(sys.argv[1]); SRC=Path(sys.argv[2]); OUT=Path(sys.argv[3])
OUT.mkdir(parents=True,exist_ok=True)
TARGET=OUT/"Lab2_DC_Circuit.ms14"
LOG=OUT/"repair-lab2.log"
DY=0

def log(m):
    s=f"[{time.strftime('%H:%M:%S')}] {m}"
    print(s,flush=True)
    with LOG.open("a",encoding="utf-8") as f:f.write(s+"\n")

def shot(n):
    import pyautogui
    pyautogui.screenshot(str(OUT/n))

def mainwin():
    from pywinauto import Desktop
    ws=[]
    for w in Desktop(backend="win32").windows():
        try:
            if "Multisim" in w.window_text() and "Select a Component" not in w.window_text():
                ws.append(w)
        except:pass
    if not ws:return None
    ws.sort(key=lambda w:-(w.rectangle().width()*w.rectangle().height()))
    return ws[0]

def focus():
    w=mainwin()
    if w:
        try:w.restore()
        except:pass
        try:w.set_focus()
        except:pass
    return w

def trial_present():
    from pywinauto import Desktop
    for backend in ("uia","win32"):
        try:
            for w in Desktop(backend=backend).windows():
                for d in w.descendants():
                    try:t=d.window_text();r=d.rectangle()
                    except:continue
                    if ("Trial" in t or "Extend Trial" in t) and r.width()>5 and r.height()>5:return True
        except:pass
    return False

def dismiss_trial():
    import pyautogui
    from pywinauto import Desktop
    for backend in ("uia","win32"):
        try:
            for w in Desktop(backend=backend).windows():
                for d in w.descendants():
                    try:t=d.window_text();r=d.rectangle()
                    except:continue
                    if ("Trial" in t or "Extend Trial" in t) and r.width()>5 and r.height()>5:
                        try:d.click_input();time.sleep(5)
                        except:pass
                        if not trial_present():return True
        except:pass
    pyautogui.click(656,520);time.sleep(8)
    return not trial_present()

def calibrate():
    global DY
    import pyautogui
    im=pyautogui.screenshot().convert("RGB")
    best=(-1,-1)
    for yy in range(185,285):
        mx=run=0
        for xx in range(370,451):
            r,g,b=im.getpixel((xx,yy))
            blue=(b>150 and r<100 and g<180)
            if blue:run+=1;mx=max(mx,run)
            else:run=0
        if mx>best[0]:best=(mx,yy)
    if best[0]<8:return False
    DY=best[1]-209
    log(f"viewport DY={DY} switch_y={best[1]}")
    return True

def add_wire():
    import pyautogui
    # Exact native pins in the saved layout: V2 right terminal and U3 left terminal.
    a=(469,398+DY); b=(568,398+DY)
    pyautogui.moveTo(*a,duration=.2);pyautogui.click();time.sleep(.5)
    pyautogui.moveTo(*b,duration=.3);pyautogui.click();time.sleep(.5)
    pyautogui.press("esc");time.sleep(1)
    log(f"wire added {a}->{b}")

def main():
    import pyautogui,shutil
    pyautogui.FAILSAFE=False
    shutil.copy2(SRC,TARGET)
    log(f"source copied size={TARGET.stat().st_size}")
    p=subprocess.Popen([str(MS),str(TARGET)])
    log(f"launch pid={p.pid}")
    time.sleep(12)
    if trial_present() and not dismiss_trial():return 11
    time.sleep(4)
    if not focus():return 12
    shot("10_opened_existing.png")
    if not calibrate():return 13

    add_wire()
    shot("20_repaired_wire.png")

    focus();pyautogui.press("f5");time.sleep(7)
    shot("30_run_repaired.png")
    pyautogui.press("f5");time.sleep(2)

    # Existing MS14: normal Save is enough and does not require a Save As dialog.
    focus();pyautogui.hotkey("ctrl","s");time.sleep(6)
    shot("40_saved_repaired.png")
    log(f"saved size={TARGET.stat().st_size} mtime={TARGET.stat().st_mtime}")

    # Close document and reopen it in the same Multisim instance.
    pyautogui.hotkey("ctrl","f4");time.sleep(4)
    pyautogui.press("esc");time.sleep(1)
    focus();pyautogui.hotkey("ctrl","o");time.sleep(2)
    from pywinauto import Desktop
    dlg=None
    for backend in ("win32","uia"):
        try:
            q=Desktop(backend=backend).window(title_re=".*[Oo]pen.*")
            if q.exists(timeout=1):dlg=q;break
        except:pass
    if not dlg:
        log("open dialog missing");return 14
    try:dlg.set_focus()
    except:pass
    pyautogui.hotkey("alt","n");time.sleep(.3)
    pyautogui.hotkey("ctrl","a");pyautogui.write(str(TARGET),interval=.002)
    pyautogui.press("enter");time.sleep(10)
    shot("50_reopened_repaired.png")

    focus();pyautogui.press("f5");time.sleep(7)
    shot("60_reopened_run.png")
    pyautogui.press("f5");time.sleep(1)
    log("REPAIR_DONE")
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except Exception:
        log(traceback.format_exc())
        try:shot("99_exception.png")
        except:pass
        sys.exit(99)
