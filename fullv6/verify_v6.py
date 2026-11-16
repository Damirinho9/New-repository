from pathlib import Path
import json, os, subprocess, sys, time, traceback

import pyautogui as pg
from pywinauto import Desktop

pg.FAILSAFE = False
ms14 = Path(sys.argv[1]).resolve()
out = ms14.parent

def windows():
    vals = []
    for backend in ("win32", "uia"):
        try:
            vals.extend(Desktop(backend=backend).windows())
        except Exception:
            pass
    return vals

def dismiss():
    targets = {"Remind Me Later", "Continue", "Evaluate", "Start Trial", "OK"}
    for _ in range(5):
        did = False
        for w in windows():
            try:
                for e in w.descendants():
                    try:
                        t = e.window_text().replace("&", "").strip()
                        r = e.rectangle()
                        if t in targets and r.width() > 5 and r.height() > 5 and e.is_visible():
                            e.click_input()
                            time.sleep(2)
                            did = True
                            break
                    except Exception:
                        pass
                if did:
                    break
            except Exception:
                pass
        if not did:
            break

def mainwin():
    candidates = []
    for w in Desktop(backend="win32").windows():
        try:
            t = w.window_text()
            r = w.rectangle()
            if "Multisim" in t and "Select a Component" not in t and r.width() > 500 and r.height() > 300:
                candidates.append(w)
        except Exception:
            pass
    candidates.sort(key=lambda w: -(w.rectangle().width() * w.rectangle().height()))
    return candidates[0] if candidates else None

def shot(name):
    w = mainwin()
    if not w:
        pg.screenshot(str(out / name))
        return
    r = w.rectangle()
    pg.screenshot(region=(max(0,r.left), max(0,r.top), r.width(), r.height())).save(str(out / name))

def main():
    ms = list(Path(r"C:\Program Files (x86)\National Instruments").rglob("Multisim.exe"))
    if not ms:
        ms = list(Path(r"C:\Program Files\National Instruments").rglob("Multisim.exe"))
    if not ms:
        raise RuntimeError("Multisim.exe not found")
    exe = ms[0]
    p = subprocess.Popen([str(exe), str(ms14)])
    time.sleep(16)
    dismiss()
    w = mainwin()
    if not w:
        raise RuntimeError("Multisim main window not found")
    try:
        w.restore()
    except Exception:
        pass
    try:
        w.maximize()
    except Exception:
        pass
    try:
        w.set_focus()
    except Exception:
        pass
    time.sleep(2)
    title = w.window_text()
    (out / "native_open_title.txt").write_text(title, encoding="utf-8")
    if "7330744_PhotoRelay_V6_FULL" not in title:
        raise RuntimeError("Expected design name absent from title: " + title)
    pg.press("f7")
    time.sleep(3)
    shot("Multisim_FULL_V6_native_open.png")

    # Try a real simulation run; a netlist error is recorded, not hidden.
    try:
        pg.press("f5")
        time.sleep(8)
        shot("Multisim_FULL_V6_native_run.png")
        messages = []
        w2 = mainwin()
        if w2:
            for backend in ("win32","uia"):
                try:
                    q = Desktop(backend=backend).window(handle=w2.handle)
                    for e in q.descendants():
                        try:
                            t=e.window_text().strip()
                            if t and ("error" in t.lower() or "warning" in t.lower() or "SPICE" in t):
                                messages.append(t)
                        except Exception:
                            pass
                except Exception:
                    pass
        (out / "native_run_messages.json").write_text(json.dumps(sorted(set(messages)), ensure_ascii=False, indent=2), encoding="utf-8")
        pg.press("f5")
        time.sleep(1)
    except Exception:
        (out / "native_run_exception.txt").write_text(traceback.format_exc(), encoding="utf-8")

    try:
        pg.hotkey("ctrl","s")
        time.sleep(2)
    except Exception:
        pass
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        (out / "native_open_exception.txt").write_text(traceback.format_exc(), encoding="utf-8")
        pg.screenshot(str(out / "native_open_failure.png"))
        sys.exit(1)
