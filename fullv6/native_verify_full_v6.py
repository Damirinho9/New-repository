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

TRIAL_TEXT = ("trial expires", "remind me later", "start trial", "evaluation")

def all_windows():
    rows = []
    for backend in ("uia", "win32"):
        try:
            for w in Desktop(backend=backend).windows():
                try:
                    rows.append((backend, w, w.window_text()))
                except Exception:
                    pass
        except Exception:
            pass
    return rows

def trial_visible():
    for backend, w, title in all_windows():
        hay = (title or "").lower()
        try:
            texts = [e.window_text().strip() for e in w.descendants() if e.window_text().strip()]
            hay += " " + " ".join(texts).lower()
        except Exception:
            pass
        if any(token in hay for token in TRIAL_TEXT):
            return True
    return False

def dismiss_trial_and_reminders():
    labels = {"Remind Me Later", "Continue", "Evaluate", "Start Trial"}
    for _ in range(6):
        clicked = False
        for backend, w, title in all_windows():
            try:
                for e in w.descendants():
                    try:
                        name = e.window_text().replace("&", "").strip()
                        if name in labels and e.is_visible():
                            e.click_input()
                            time.sleep(3)
                            clicked = True
                            break
                    except Exception:
                        pass
            except Exception:
                pass
            if clicked:
                break
        if clicked:
            continue

        # Multisim 14.3 trial dialog can be a custom-drawn child that pywinauto
        # does not expose. The Windows runner is 1024x768; its verified
        # "Remind Me Later" button is centred at about (640,520).
        if trial_visible():
            pg.click(640, 520)
            time.sleep(6)
            clicked = True
        if not clicked:
            break

def multisim_main_windows():
    candidates = []
    for backend, w, title in all_windows():
        if "multisim" not in (title or "").lower():
            continue
        if "select a component" in (title or "").lower():
            continue
        try:
            r = w.rectangle()
            area = max(0, r.width()) * max(0, r.height())
            candidates.append((area, w, title))
        except Exception:
            pass
    candidates.sort(key=lambda z: -z[0])
    return candidates

def main_window():
    rows = multisim_main_windows()
    return (rows[0][1], rows[0][2]) if rows else (None, "")

def target_title(timeout=35):
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        dismiss_trial_and_reminders()
        for _, w, title in multisim_main_windows():
            last = title
            if TARGET.stem.lower() in (title or "").lower():
                try:
                    w.restore()
                except Exception:
                    pass
                try:
                    w.set_focus()
                except Exception:
                    pass
                return w, title
        time.sleep(1)
    return None, last

def focus_and_fit():
    w, title = target_title(timeout=8)
    if not w:
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

def launch_and_wait():
    subprocess.Popen([str(MULTISIM), str(TARGET)])
    time.sleep(12)
    dismiss_trial_and_reminders()
    w, title = target_title(timeout=35)
    if not w:
        pg.screenshot(str(OUT / "blocked_or_wrong_title.png"))
        raise RuntimeError(f"target file not visible in Multisim title: {title!r}")
    return w, title

w1, title1 = launch_and_wait()
title1 = shot("01_full_v6_opened.png")

# Force a genuine Multisim save. No Save As is used: Ctrl+S writes the opened native design.
w, _ = target_title(timeout=10)
if not w:
    raise RuntimeError("target Multisim window disappeared before save")
pg.hotkey("ctrl", "s")
time.sleep(7)
dismiss_trial_and_reminders()
_, title_saved = target_title(timeout=15)
title_saved = shot("02_full_v6_saved_by_multisim.png")

subprocess.run(["taskkill", "/IM", "Multisim.exe", "/T", "/F"], capture_output=True)
time.sleep(5)

w2, title2 = launch_and_wait()
title2 = shot("03_full_v6_reopened.png")

info = {
    "opened_title": title1,
    "saved_title": title_saved,
    "reopened_title": title2,
    "save_close_reopen": True,
    "target": str(TARGET),
    "size_bytes": TARGET.stat().st_size,
}
(OUT / "native_gui_verification.json").write_text(
    json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
)
subprocess.run(["taskkill", "/IM", "Multisim.exe", "/T", "/F"], capture_output=True)
print(json.dumps(info, ensure_ascii=False, indent=2))
