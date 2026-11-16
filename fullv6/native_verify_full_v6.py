import json
import subprocess
import sys
import time
from pathlib import Path

import pyautogui as pg
from pywinauto import Desktop

MULTISIM = Path(sys.argv[1])
TARGET = Path(sys.argv[2]).resolve()
OUT = Path(sys.argv[3]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
pg.FAILSAFE = False

def windows():
    out = []
    for backend in ("uia", "win32"):
        try:
            for w in Desktop(backend=backend).windows():
                try:
                    title = w.window_text()
                    if "Multisim" in title:
                        out.append((backend, w, title))
                except Exception:
                    pass
        except Exception:
            pass
    return out

def dismiss():
    labels = {"Remind Me Later", "Continue", "Evaluate", "Start Trial", "OK"}
    for _ in range(5):
        did = False
        for backend in ("uia", "win32"):
            try:
                for w in Desktop(backend=backend).windows():
                    try:
                        title = w.window_text()
                    except Exception:
                        title = ""
                    for e in w.descendants():
                        try:
                            name = e.window_text().replace("&", "").strip()
                            if name in labels and e.is_visible():
                                # Do not press OK in a Save/overwrite confirmation blindly.
                                if name == "OK" and not any(k in title.lower() for k in ("trial", "evaluation", "remind")):
                                    continue
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
            if did:
                break
        if not did:
            break

def main_window():
    candidates = []
    for backend, w, title in windows():
        try:
            r = w.rectangle()
            area = max(0, r.width()) * max(0, r.height())
            if "Select a Component" not in title:
                candidates.append((area, w, title))
        except Exception:
            pass
    if not candidates:
        return None, ""
    candidates.sort(key=lambda z: -z[0])
    return candidates[0][1], candidates[0][2]

def focus_and_fit():
    w, title = main_window()
    if not w:
        return None, title
    try:
        w.restore()
    except Exception:
        pass
    try:
        w.set_focus()
    except Exception:
        pass
    time.sleep(1)
    pg.press("f7")
    time.sleep(3)
    return w, title

def shot(name):
    w, title = focus_and_fit()
    pg.screenshot(str(OUT / name))
    if w:
        try:
            r = w.rectangle()
            left, top = max(0, r.left), max(0, r.top)
            width, height = max(10, r.width()), max(10, r.height())
            pg.screenshot(region=(left, top, width, height)).save(str(OUT / ("window_" + name)))
        except Exception:
            pass
    return title

def launch():
    subprocess.Popen([str(MULTISIM), str(TARGET)])
    time.sleep(14)
    dismiss()
    time.sleep(3)

launch()
title1 = shot("01_full_v6_opened.png")
if TARGET.stem.lower() not in title1.lower():
    raise RuntimeError(f"target file not visible in Multisim title after first open: {title1!r}")

# Force a genuine application save so the submitted bytes have passed through Multisim itself.
w, _ = focus_and_fit()
pg.hotkey("ctrl", "s")
time.sleep(6)
dismiss()
title_saved = shot("02_full_v6_saved_by_multisim.png")

subprocess.run(["taskkill", "/IM", "Multisim.exe", "/T", "/F"], capture_output=True)
time.sleep(4)

launch()
title2 = shot("03_full_v6_reopened.png")
if TARGET.stem.lower() not in title2.lower():
    raise RuntimeError(f"target file not visible in Multisim title after reopen: {title2!r}")

info = {
    "opened_title": title1,
    "saved_title": title_saved,
    "reopened_title": title2,
    "save_close_reopen": True,
    "target": str(TARGET),
    "size_bytes": TARGET.stat().st_size,
}
(OUT / "native_gui_verification.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
subprocess.run(["taskkill", "/IM", "Multisim.exe", "/T", "/F"], capture_output=True)
print(json.dumps(info, ensure_ascii=False, indent=2))
