import os, sys, time, subprocess, traceback
from pathlib import Path

MULTISIM = Path(sys.argv[1])
CIR = Path(sys.argv[2])
TARGET = Path(sys.argv[3])
OUT = Path(sys.argv[4])
OUT.mkdir(parents=True, exist_ok=True)
LOG = OUT / "python-gui.log"

def log(msg):
    s = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(s, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(s+"\n")

def shot(name):
    try:
        import pyautogui
        p = OUT / name
        pyautogui.screenshot(str(p))
        log(f"screenshot {p}")
    except Exception as e:
        log(f"screenshot failed: {e}")

def dump_windows(name):
    try:
        from pywinauto import Desktop
        lines=[]
        for backend in ("win32","uia"):
            try:
                for w in Desktop(backend=backend).windows():
                    try:
                        lines.append(f"{backend}\t{w.window_text()}\tclass={w.class_name()}\trect={w.rectangle()}")
                    except Exception:
                        pass
            except Exception as e:
                lines.append(f"{backend} ERROR {e}")
        (OUT/name).write_text("\n".join(lines), encoding="utf-8")
    except Exception as e:
        log(f"dump_windows failed: {e}")

def find_multisim_window():
    from pywinauto import Desktop
    candidates=[]
    for w in Desktop(backend="win32").windows():
        try:
            if "Multisim" in w.window_text():
                candidates.append(w)
        except Exception:
            pass
    return candidates[0] if candidates else None

def focus_main():
    w=find_multisim_window()
    if w:
        try: w.restore()
        except Exception: pass
        try: w.set_focus()
        except Exception: pass
        return w
    return None

def trial_present():
    try:
        from pywinauto import Desktop
        for w in Desktop(backend="uia").windows():
            try:
                for desc in w.descendants():
                    try:
                        txt=desc.window_text()
                    except Exception:
                        txt=""
                    if txt in ("Log in to Extend Trial","Begin 7 Day Trial"):
                        return True
            except Exception:
                pass
    except Exception:
        pass
    return False

def click_trial():
    import pyautogui
    from pywinauto import Desktop
    dump_windows("windows_before_trial.txt")

    # First try any real clickable trial control that pywinauto can see.
    for backend in ("win32","uia"):
        try:
            for w in Desktop(backend=backend).windows():
                try:
                    for desc in w.descendants():
                        try:
                            txt=desc.window_text()
                        except Exception:
                            txt=""
                        if "Trial" in txt or "Extend Trial" in txt:
                            try:
                                rect=desc.rectangle()
                                log(f"trial candidate backend={backend} text={txt!r} rect={rect}")
                                # Ignore ghost UIA elements with an empty rectangle.
                                if rect.width() > 5 and rect.height() > 5:
                                    desc.click_input()
                                    time.sleep(5)
                                    if not trial_present():
                                        log("trial dialog disappeared after pywinauto click_input")
                                        return True
                            except Exception as e:
                                log(f"click_input failed: {e}")
                except Exception:
                    pass
        except Exception as e:
            log(f"backend {backend} trial scan failed: {e}")

    # The GitHub Windows desktop is fixed at 1024x768 in these runs.
    # NI's modal is consistently centered and the visible Begin 7 Day Trial
    # button center is x=656,y=520.
    log("trial still visible; using real pyautogui click at 656,520")
    pyautogui.moveTo(656,520,duration=.5)
    pyautogui.mouseDown()
    time.sleep(.15)
    pyautogui.mouseUp()
    time.sleep(8)
    shot("11a_after_physical_trial_click.png")
    if not trial_present():
        log("trial dialog disappeared after physical pyautogui click")
        return True

    # Keyboard fallback: activate Multisim and try common tab navigation.
    log("trial still visible after physical click; trying keyboard navigation")
    focus_main()
    pyautogui.click(500,190)
    time.sleep(.5)
    # Tab sequence around the licensing dialog, with screenshots for diagnosis.
    for n in range(1,9):
        pyautogui.press("tab")
        time.sleep(.25)
        if n in (3,5,6,7):
            pyautogui.press("enter")
            time.sleep(3)
            if not trial_present():
                log(f"trial dialog disappeared after keyboard tab/enter n={n}")
                return True
    log("trial dialog remains after all real-input methods")
    return False

def handle_standard_dialog(title_re, file_path, action_names):
    from pywinauto import Desktop
    import pyautogui
    for _ in range(20):
        try:
            dlg=Desktop(backend="win32").window(title_re=title_re)
            if dlg.exists(timeout=.5):
                log(f"found dialog {dlg.window_text()!r}")
                try: dlg.set_focus()
                except Exception: pass
                edits=dlg.descendants(class_name="Edit")
                if edits:
                    e=edits[-1]
                    try:
                        e.set_edit_text(str(file_path))
                    except Exception:
                        e.click_input(); pyautogui.hotkey("ctrl","a"); pyautogui.write(str(file_path), interval=.002)
                else:
                    pyautogui.write(str(file_path), interval=.002)
                for name in action_names:
                    try:
                        b=dlg.child_window(title_re=name, class_name="Button")
                        if b.exists(timeout=.3):
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

def main():
    import pyautogui
    pyautogui.FAILSAFE=False
    log(f"launching {MULTISIM}")
    p=subprocess.Popen([str(MULTISIM)])
    log(f"PID={p.pid}")
    time.sleep(10)
    shot("10_license_before_click.png")
    trial_ok=click_trial()
    shot("11_after_trial_click.png")
    if not trial_ok:
        log("Trial could not be started with real GUI input; stopping before Open.")
        return 14
    dump_windows("windows_after_trial.txt")

    w=focus_main()
    if w:
        log(f"Multisim top window after trial: {w.window_text()!r} rect={w.rectangle()}")
    else:
        log("No Multisim top-level window found after trial click")
        return 15
    time.sleep(3)

    focus_main()
    pyautogui.hotkey("ctrl","o")
    time.sleep(2)
    if not handle_standard_dialog(r".*[Oo]pen.*", CIR, (r"&Open", r"Open")):
        log("Open dialog wrapper not found, keyboard fallback")
        pyautogui.write(str(CIR), interval=.002)
        pyautogui.press("enter")
    log("Open request submitted")
    time.sleep(18)
    shot("20_after_open.png")
    dump_windows("windows_after_open.txt")

    focus_main()
    pyautogui.hotkey("ctrl","shift","s")
    time.sleep(2)
    saved=handle_standard_dialog(r".*[Ss]ave.*", TARGET, (r"&Save", r"Save"))
    if not saved:
        log("Ctrl+Shift+S did not produce Save As; trying Alt+F then A")
        focus_main(); pyautogui.hotkey("alt","f"); time.sleep(.7); pyautogui.press("a"); time.sleep(2)
        saved=handle_standard_dialog(r".*[Ss]ave.*", TARGET, (r"&Save", r"Save"))
    time.sleep(8)
    pyautogui.press("enter")
    time.sleep(3)
    shot("30_after_save.png")
    dump_windows("windows_after_save.txt")

    if not TARGET.exists():
        roots=[OUT, Path(os.environ.get("USERPROFILE","C:/Users/runneradmin")), Path.cwd()]
        found=[]
        for r in roots:
            try: found.extend(r.rglob("*.ms14"))
            except Exception: pass
        found=sorted(set(found), key=lambda x:x.stat().st_mtime if x.exists() else 0, reverse=True)
        (OUT/"python-found-ms14.txt").write_text("\n".join(map(str,found)), encoding="utf-8")
        if found:
            import shutil
            shutil.copy2(found[0], TARGET)
            log(f"normalized discovered ms14 {found[0]} -> {TARGET}")

    if TARGET.exists():
        log(f"SUCCESS ms14={TARGET} size={TARGET.stat().st_size}")
        return 0
    log("MS14 not created")
    return 20

if __name__=="__main__":
    try:
        sys.exit(main())
    except Exception:
        log(traceback.format_exc())
        shot("99_exception.png")
        sys.exit(99)
