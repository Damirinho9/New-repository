import os, sys, time, subprocess, traceback
from pathlib import Path

MULTISIM=Path(sys.argv[1]); CIR=Path(sys.argv[2]); TARGET=Path(sys.argv[3]); OUT=Path(sys.argv[4])
OUT.mkdir(parents=True,exist_ok=True)
LOG=OUT/"python-gui.log"

def log(m):
    s=f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {m}"
    print(s,flush=True)
    with LOG.open("a",encoding="utf-8") as f:f.write(s+"\n")

def shot(n):
    try:
        import pyautogui
        p=OUT/n; pyautogui.screenshot(str(p)); log(f"screenshot {p}")
    except Exception as e: log(f"screenshot error {e}")

def mainwin():
    from pywinauto import Desktop
    wins=[]
    for w in Desktop(backend="win32").windows():
        try:
            t=w.window_text()
            if "Multisim" in t and "Select a Component" not in t and "Arbitrary SPICE" not in t:
                wins.append(w)
        except: pass
    wins.sort(key=lambda w:("Design" not in w.window_text(),-(w.rectangle().width()*w.rectangle().height())))
    return wins[0] if wins else None

def focus_main():
    w=mainwin()
    if w:
        try:w.restore()
        except:pass
        try:w.set_focus()
        except:pass
    return w

def trial_present():
    from pywinauto import Desktop
    for w in Desktop(backend="uia").windows():
        try:
            for d in w.descendants():
                try:t=d.window_text()
                except:t=""
                if t in ("Log in to Extend Trial","Begin 7 Day Trial"):return True
        except:pass
    return False

def dismiss_trial():
    import pyautogui
    from pywinauto import Desktop
    for backend in ("uia","win32"):
        try:
            for w in Desktop(backend=backend).windows():
                for d in w.descendants():
                    try:t=d.window_text(); r=d.rectangle()
                    except:continue
                    if ("Trial" in t or "Extend Trial" in t) and r.width()>5 and r.height()>5:
                        try:
                            d.click_input(); time.sleep(5)
                            if not trial_present(): return True
                        except:pass
        except:pass
    pyautogui.click(656,520); time.sleep(8)
    return not trial_present()

def dump_dialog(dlg,path):
    lines=[]
    for d in dlg.descendants():
        try:
            lines.append(f"{d.window_text()!r}\tclass={d.class_name()}\tctrl={getattr(d.element_info,'control_type','')}\trect={d.rectangle()}")
        except:pass
    (OUT/path).write_text("\n".join(lines),encoding="utf-8")

def clean_netlist():
    out=[]
    for line in CIR.read_text(encoding="utf-8",errors="replace").splitlines():
        u=line.strip().upper()
        if u.startswith(".TRAN") or u.startswith(".PROBE") or u==".END":continue
        out.append(line)
    return "\r\n".join(out).strip()+"\r\n"

def open_component_browser():
    import pyautogui
    from pywinauto import Desktop
    w=focus_main()
    if not w:return None
    try:w.menu_select("Place->Component...")
    except Exception as e:
        log(f"menu_select Place/Component failed: {e}")
        pyautogui.hotkey("alt","p"); time.sleep(.5); pyautogui.press("c")
    time.sleep(2)
    for backend in ("uia","win32"):
        try:
            d=Desktop(backend=backend).window(title_re=".*Select a Component.*")
            if d.exists(timeout=2):
                try:d.set_focus()
                except:pass
                log(f"component browser backend={backend} rect={d.rectangle()}")
                return d
        except:pass
    return None

def choose_spice_block(dlg):
    import pyautogui
    from pywinauto import Desktop
    title=dlg.window_text()
    u=Desktop(backend="uia").window(title=title)
    dump_dialog(u,"component-browser-controls.txt")
    r=u.rectangle()

    # Set Group=Basic if exposed. Database is normally first combo, Group second.
    combos=[]
    for d in u.descendants():
        try:
            if getattr(d.element_info,"control_type","")=="ComboBox":combos.append(d)
        except:pass
    if len(combos)>=2:
        try:combos[1].select("Basic");time.sleep(1)
        except:pass

    # Select BASIC_VIRTUAL family if it is exposed.
    for d in u.descendants():
        try:
            if d.window_text().strip().upper()=="BASIC_VIRTUAL" and d.rectangle().width()>5:
                d.click_input();time.sleep(1);break
        except:pass

    # Type exact component name in Component field (upper-middle of dialog).
    pyautogui.click(r.left+300,r.top+55)
    pyautogui.hotkey("ctrl","a")
    pyautogui.write("ARBITRARY_SPICE_BLOCK",interval=.02)
    time.sleep(2)

    # Select exact list row where available.
    for d in u.descendants():
        try:
            if d.window_text().strip().upper()=="ARBITRARY_SPICE_BLOCK" and d.rectangle().width()>5:
                d.click_input();time.sleep(.5)
        except:pass

    # OK
    for d in u.descendants():
        try:
            if d.window_text().replace("&","").strip()=="OK" and d.rectangle().width()>5:
                d.click_input();time.sleep(2);return True
        except:pass
    pyautogui.press("enter");time.sleep(2)
    return True

def place_block(nettext):
    import pyautogui, pyperclip
    from pywinauto import Desktop
    dlg=open_component_browser()
    if not dlg:
        log("component browser missing");return False
    shot("40_component_browser.png")
    if not choose_spice_block(dlg):return False

    w=focus_main()
    rr=w.rectangle() if w else None
    x=(rr.left+520 if rr else 520); y=(rr.top+300 if rr else 330)
    pyautogui.click(x,y);time.sleep(2);pyautogui.press("esc");time.sleep(1)
    shot("41_spiceblock_placed.png")

    pyautogui.doubleClick(x,y,interval=.15);time.sleep(3)
    prop=None
    for backend in ("uia","win32"):
        try:
            p=Desktop(backend=backend).window(title_re=".*Arbitrary SPICE.*")
            if p.exists(timeout=2):prop=p;break
        except:pass
    if not prop:
        log("properties dialog missing");return False
    try:prop.set_focus()
    except:pass
    dump_dialog(prop,"spiceblock-properties-controls.txt")
    shot("42_spiceblock_properties.png")

    # Ensure Value tab.
    for d in prop.descendants():
        try:
            if d.window_text().strip()=="Value" and d.rectangle().width()>5:
                d.click_input();time.sleep(1);break
        except:pass

    edits=[]
    for d in prop.descendants():
        try:
            if "Edit" in d.class_name() or getattr(d.element_info,"control_type","")=="Edit":
                r=d.rectangle();edits.append((r.width()*r.height(),d,r))
        except:pass
    pyperclip.copy(nettext)
    if edits:
        edits.sort(reverse=True,key=lambda z:z[0]);_,e,r=edits[0]
        log(f"netlist edit rect={r}")
        try:e.click_input()
        except:pyautogui.click((r.left+r.right)//2,(r.top+r.bottom)//2)
    else:
        r=prop.rectangle();pyautogui.click(r.left+250,r.top+250)
    pyautogui.hotkey("ctrl","a");pyautogui.hotkey("ctrl","v");time.sleep(2)
    shot("43_netlist_pasted.png")

    for d in prop.descendants():
        try:
            if d.window_text().replace("&","").strip()=="OK" and d.rectangle().width()>5:
                d.click_input();time.sleep(3);shot("44_spiceblock_ready.png");return True
        except:pass
    pyautogui.press("enter");time.sleep(3);shot("44_spiceblock_ready.png")
    return True

def save_as():
    import pyautogui
    from pywinauto import Desktop
    w=focus_main()
    try:w.menu_select("File->Save As...")
    except:
        pyautogui.hotkey("alt","f");time.sleep(.5);pyautogui.press("a")
    time.sleep(2)
    dlg=None
    for backend in ("win32","uia"):
        try:
            d=Desktop(backend=backend).window(title_re=".*[Ss]ave.*")
            if d.exists(timeout=1):dlg=d;break
        except:pass
    if not dlg:
        log("Save As dialog missing");return False
    try:dlg.set_focus()
    except:pass
    edits=dlg.descendants(class_name="Edit")
    if edits:
        e=edits[-1]
        try:e.set_edit_text(str(TARGET))
        except:
            e.click_input();pyautogui.hotkey("ctrl","a");pyautogui.write(str(TARGET),interval=.002)
    else:pyautogui.write(str(TARGET),interval=.002)
    clicked=False
    for b in dlg.descendants(class_name="Button"):
        try:
            if b.window_text().replace("&","").strip().lower()=="save":
                b.click_input();clicked=True;break
        except:pass
    if not clicked:pyautogui.press("enter")
    time.sleep(8);pyautogui.press("enter");time.sleep(2)
    shot("50_saved_ms14.png")
    return TARGET.exists()

def main():
    import pyautogui
    pyautogui.FAILSAFE=False
    nettext=clean_netlist()
    (OUT/"arbitrary_spice_block_netlist.txt").write_text(nettext,encoding="utf-8")

    log(f"launching {MULTISIM}")
    p=subprocess.Popen([str(MULTISIM)]);log(f"PID={p.pid}")
    time.sleep(10);shot("10_license_before_click.png")
    if trial_present() and not dismiss_trial():
        log("trial activation failed");return 11
    time.sleep(3)
    if not focus_main():
        log("main window missing");return 12

    # Create a genuine Multisim design using NI's supported Arbitrary SPICE Block.
    pyautogui.hotkey("ctrl","n");time.sleep(2)
    if not place_block(nettext):return 20
    if TARGET.exists():TARGET.unlink()
    if not save_as():
        log("MS14 not created");return 21
    log(f"SUCCESS ms14={TARGET} size={TARGET.stat().st_size}")
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except Exception:
        log(traceback.format_exc());shot("99_exception.png");sys.exit(99)
