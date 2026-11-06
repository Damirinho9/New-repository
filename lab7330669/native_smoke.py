import os, sys, time, subprocess, traceback
from pathlib import Path

MULTISIM = Path(sys.argv[1])
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
TARGET = OUT / "Native_GUI_Smoke.ms14"
LOG = OUT / "native-gui-smoke.log"

def log(msg):
    s = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(s, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(s + "\n")

def shot(name):
    try:
        import pyautogui
        p = OUT / name
        pyautogui.screenshot(str(p))
        log(f"screenshot={p}")
    except Exception as e:
        log(f"screenshot failed: {e}")

def windows_dump(name):
    try:
        from pywinauto import Desktop
        lines = []
        for backend in ("win32", "uia"):
            try:
                for w in Desktop(backend=backend).windows():
                    try:
                        lines.append(f"{backend}\t{w.window_text()}\t{w.class_name()}\t{w.rectangle()}")
                    except Exception:
                        pass
            except Exception as e:
                lines.append(f"{backend} ERROR {e}")
        (OUT / name).write_text("\n".join(lines), encoding="utf-8")
    except Exception as e:
        log(f"windows dump failed: {e}")

def find_main():
    from pywinauto import Desktop
    wins = []
    for w in Desktop(backend="win32").windows():
        try:
            t = w.window_text()
            if "Multisim" in t and "Select a Component" not in t:
                wins.append(w)
        except Exception:
            pass
    if not wins:
        return None
    wins.sort(key=lambda w: -(w.rectangle().width() * w.rectangle().height()))
    return wins[0]

def focus_main():
    w = find_main()
    if w:
        try: w.restore()
        except Exception: pass
        try: w.set_focus()
        except Exception: pass
    return w

def trial_present():
    from pywinauto import Desktop
    for backend in ("uia", "win32"):
        try:
            for w in Desktop(backend=backend).windows():
                try:
                    for d in w.descendants():
                        try:
                            t = d.window_text()
                            r = d.rectangle()
                        except Exception:
                            continue
                        if ("Trial" in t or "Extend Trial" in t) and r.width() > 5 and r.height() > 5:
                            return True
                except Exception:
                    pass
        except Exception:
            pass
    return False

def dismiss_trial():
    import pyautogui
    from pywinauto import Desktop
    for backend in ("uia", "win32"):
        try:
            for w in Desktop(backend=backend).windows():
                for d in w.descendants():
                    try:
                        t = d.window_text()
                        r = d.rectangle()
                    except Exception:
                        continue
                    if ("Trial" in t or "Extend Trial" in t) and r.width() > 5 and r.height() > 5:
                        try:
                            log(f"trial candidate {t!r} rect={r}")
                            d.click_input()
                            time.sleep(5)
                            if not trial_present():
                                return True
                        except Exception as e:
                            log(f"trial click failed: {e}")
        except Exception:
            pass

    # Fallback verified on the GitHub Windows desktop used for Multisim 14.3.
    pyautogui.click(656, 520)
    time.sleep(8)
    return not trial_present()

def standard_file_dialog(title_re, path, button_name):
    from pywinauto import Desktop
    import pyautogui
    for _ in range(30):
        try:
            dlg = Desktop(backend="win32").window(title_re=title_re)
            if dlg.exists(timeout=.3):
                try: dlg.set_focus()
                except Exception: pass
                edits = dlg.descendants(class_name="Edit")
                if edits:
                    e = edits[-1]
                    try:
                        e.set_edit_text(str(path))
                    except Exception:
                        e.click_input()
                        pyautogui.hotkey("ctrl", "a")
                        pyautogui.write(str(path), interval=.002)
                else:
                    pyautogui.write(str(path), interval=.002)
                buttons = dlg.descendants(class_name="Button")
                for b in buttons:
                    try:
                        if b.window_text().replace("&","").strip().lower() == button_name.lower():
                            b.click_input()
                            return True
                    except Exception:
                        pass
                pyautogui.press("enter")
                return True
        except Exception:
            pass
        time.sleep(.5)
    return False

def open_component_dialog():
    import pyautogui
    from pywinauto import Desktop
    focus_main()
    pyautogui.hotkey("ctrl", "w")
    for _ in range(30):
        try:
            dlg = Desktop(backend="win32").window(title="Select a Component")
            if dlg.exists(timeout=.3):
                try: dlg.set_focus()
                except Exception: pass
                return dlg
        except Exception:
            pass
        time.sleep(.4)
    return None

def place_component(search_text, x, y):
    import pyautogui
    dlg = open_component_dialog()
    if not dlg:
        log(f"Select a Component did not open for {search_text}")
        return False

    r = dlg.rectangle()
    log(f"component dialog {search_text}: rect={r}")

    # Component field from the native Multisim 14.3 Win32 dialog.
    pyautogui.click(r.left + 300, r.top + 65)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.write(search_text, interval=.04)
    time.sleep(2)

    # Select first matching component row, then OK.
    pyautogui.click(r.left + 310, r.top + 89)
    time.sleep(.5)
    pyautogui.click(r.right - 50, r.top + 50)
    time.sleep(2)

    # Component follows cursor.
    pyautogui.click(x, y)
    time.sleep(1)
    pyautogui.press("esc")
    time.sleep(1)
    return True

def save_new_design():
    import pyautogui
    focus_main()
    if TARGET.exists():
        TARGET.unlink()
    pyautogui.hotkey("ctrl", "s")
    time.sleep(2)
    if not standard_file_dialog(r".*[Ss]ave.*", TARGET, "save"):
        log("Save dialog was not found")
        return False
    time.sleep(8)
    pyautogui.press("enter")
    time.sleep(2)
    return TARGET.exists()

def close_reopen():
    import pyautogui
    # Close Multisim completely, then reopen the saved native file directly in Multisim.
    focus_main()
    pyautogui.hotkey("alt", "f4")
    time.sleep(5)
    try:
        subprocess.run(["taskkill", "/IM", "Multisim.exe", "/T", "/F"], capture_output=True, text=True, timeout=10)
    except Exception:
        pass
    time.sleep(2)

    p = subprocess.Popen([str(MULTISIM), str(TARGET)])
    log(f"relaunch pid={p.pid} file={TARGET}")
    time.sleep(14)

    w = focus_main()
    title = w.window_text() if w else ""
    log(f"reopened window title={title!r}")
    return "native_gui_smoke" in title.lower()

def run_test():
    import pyautogui
    focus_main()
    pyautogui.press("f5")
    time.sleep(5)
    windows_dump("windows_after_run.txt")
    shot("50_after_run.png")
    # Stop again if simulation started.
    pyautogui.press("f5")
    time.sleep(2)
    return True

def main():
    import pyautogui
    pyautogui.FAILSAFE = False

    log(f"launching={MULTISIM}")
    p = subprocess.Popen([str(MULTISIM)])
    log(f"pid={p.pid}")
    time.sleep(10)
    shot("10_first_launch.png")

    if trial_present():
        if not dismiss_trial():
            log("trial dialog could not be dismissed")
            return 11

    if not focus_main():
        log("Multisim main window not found")
        return 12

    # Native design only. No CIR/SPICE import.
    # Multisim starts with Design1 already open, so do not invoke the New Design wizard.

    # Native smoke circuit content: real database components.
    if not place_component("RESISTOR", 500, 350):
        return 20
    if not place_component("GROUND", 600, 430):
        log("GROUND placement failed; continuing save/reopen smoke check")

    shot("20_native_components.png")

    if not save_new_design():
        log("native MS14 was not saved")
        return 21

    size = TARGET.stat().st_size
    log(f"saved native ms14={TARGET} size={size}")
    if size < 1000:
        log("saved file is unexpectedly small")
        return 22

    shot("30_saved_native_ms14.png")

    if not close_reopen():
        log("reopen verification failed")
        return 23

    shot("40_reopened_native_ms14.png")
    run_test()

    log("NATIVE_GUI_SMOKE_OK")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        log(traceback.format_exc())
        shot("99_exception.png")
        sys.exit(99)
