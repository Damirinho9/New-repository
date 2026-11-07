import os, sys, time, subprocess, traceback, re
from pathlib import Path

MULTISIM=Path(sys.argv[1]); OUT=Path(sys.argv[2])
OUT.mkdir(parents=True,exist_ok=True)
TARGET=OUT/"Lab2_DC_Circuit.ms14"
LOG=OUT/"lab2-native.log"

def log(m):
    s=f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {m}"
    print(s,flush=True)
    with LOG.open("a",encoding="utf-8") as f:f.write(s+"\n")

def shot(n):
    try:
        import pyautogui
        p=OUT/n; pyautogui.screenshot(str(p)); log(f"screenshot={p}")
    except Exception as e:log(f"shot failed {e}")

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

def comp_dialog():
    import pyautogui
    from pywinauto import Desktop
    focus();pyautogui.hotkey("ctrl","w")
    for _ in range(30):
        try:
            d=Desktop(backend="win32").window(title="Select a Component")
            if d.exists(timeout=.25):
                try:d.set_focus()
                except:pass
                return d
        except:pass
        time.sleep(.35)
    return None

def place(name,x,y,rotate=0):
    import pyautogui
    d=comp_dialog()
    if not d:
        log(f"component dialog missing: {name}");return False
    r=d.rectangle()
    pyautogui.click(r.left+300,r.top+65)
    pyautogui.hotkey("ctrl","a");pyautogui.write(name,interval=.03);time.sleep(1.5)
    pyautogui.click(r.left+310,r.top+89);time.sleep(.4)
    pyautogui.click(r.right-50,r.top+50);time.sleep(1.3)
    for _ in range(rotate):
        pyautogui.hotkey("ctrl","r");time.sleep(.3)
    pyautogui.click(x,y);time.sleep(.7);pyautogui.press("esc");time.sleep(.5)
    log(f"placed {name} at {x},{y} rot={rotate}")
    return True

def modal_dialog():
    from pywinauto import Desktop
    for backend in ("uia","win32"):
        try:
            wins=Desktop(backend=backend).windows()
            for w in wins:
                try:
                    t=w.window_text()
                    if t and "Multisim" not in t and "Select a Component" not in t:
                        r=w.rectangle()
                        if r.width()>250 and r.height()>150:return w
                except:pass
        except:pass
    return None

def set_value(x,y,value):
    import pyautogui
    focus();pyautogui.doubleClick(x,y,interval=.15);time.sleep(2)
    d=modal_dialog()
    if not d:
        log(f"value dialog missing at {x},{y}");pyautogui.press("esc");return False
    try:
        # click Value tab if exposed
        for e in d.descendants():
            try:
                if e.window_text().strip()=="Value" and e.rectangle().width()>5:
                    e.click_input();time.sleep(.7);break
            except:pass
        edits=[]
        for e in d.descendants():
            try:
                ct=getattr(e.element_info,"control_type","")
                if ct=="Edit" or "Edit" in e.class_name():
                    r=e.rectangle();cur=e.window_text()
                    if r.width()>30 and r.height()>10:
                        edits.append((r.width()*r.height(),e,cur,r))
            except:pass
        edits.sort(reverse=True,key=lambda z:z[0])
        log("edits: "+" | ".join([f"{q[2]!r}@{q[3]}" for q in edits[:8]]))
        chosen=None
        # Prefer an existing numeric/unit value field over reference designator.
        for _,e,cur,r in edits:
            u=cur.strip()
            if re.search(r"\d",u) and not re.fullmatch(r"[A-Za-z]+\d+",u):
                chosen=e;break
        if chosen is None and edits:chosen=edits[0][1]
        if chosen is None:
            pyautogui.press("esc");return False
        try:chosen.set_edit_text(value)
        except:
            chosen.click_input();pyautogui.hotkey("ctrl","a");pyautogui.write(value,interval=.05)
        time.sleep(.5)
        pyautogui.press("enter");time.sleep(1.2)
        log(f"set value {value} at {x},{y}")
        return True
    except Exception as e:
        log(f"set_value error {e}");pyautogui.press("esc");return False

def wire(points):
    import pyautogui
    focus()
    pyautogui.click(*points[0]);time.sleep(.2)
    for p in points[1:]:
        pyautogui.click(*p);time.sleep(.2)
    pyautogui.press("esc");time.sleep(.25)

def save_as():
    import pyautogui
    from pywinauto import Desktop
    focus();pyautogui.hotkey("ctrl","shift","s");time.sleep(2)
    d=None
    for backend in ("win32","uia"):
        try:
            q=Desktop(backend=backend).window(title_re=".*[Ss]ave.*")
            if q.exists(timeout=1):d=q;break
        except:pass
    if not d:
        log("save dialog missing");return False
    try:d.set_focus()
    except:pass
    edits=d.descendants(class_name="Edit")
    if edits:
        e=edits[-1]
        try:e.set_edit_text(str(TARGET))
        except:
            e.click_input();pyautogui.hotkey("ctrl","a");pyautogui.write(str(TARGET),interval=.002)
    else:pyautogui.write(str(TARGET),interval=.002)
    pyautogui.press("enter");time.sleep(7);pyautogui.press("enter");time.sleep(2)
    return TARGET.exists()

def reopen_in_app():
    import pyautogui
    from pywinauto import Desktop
    focus();pyautogui.hotkey("ctrl","f4");time.sleep(4);pyautogui.press("enter");time.sleep(1)
    focus();pyautogui.hotkey("ctrl","o");time.sleep(2)
    d=None
    for backend in ("win32","uia"):
        try:
            q=Desktop(backend=backend).window(title_re=".*[Oo]pen.*")
            if q.exists(timeout=1):d=q;break
        except:pass
    if not d:return False
    try:d.set_focus()
    except:pass
    edits=d.descendants(class_name="Edit")
    if edits:
        e=edits[-1]
        try:e.set_edit_text(str(TARGET))
        except:
            e.click_input();pyautogui.hotkey("ctrl","a");pyautogui.write(str(TARGET),interval=.002)
    else:pyautogui.write(str(TARGET),interval=.002)
    pyautogui.press("enter");time.sleep(10)
    w=focus();title=w.window_text() if w else ""
    log(f"reopened title={title!r}")
    shot("60_reopened.png")
    return "Lab2_DC_Circuit".lower() in title.lower()

def main():
    import pyautogui
    pyautogui.FAILSAFE=False
    p=subprocess.Popen([str(MULTISIM)]);log(f"launch pid={p.pid}");time.sleep(10)
    if trial_present() and not dismiss_trial():return 11
    if not focus():return 12
    time.sleep(2)

    # Figure 2.6 layout: three vertical branches between common c and a.
    # x positions: left 420, middle 610, right 800. top y=220, bottom y=500.
    # Place resistors rotated vertical.
    items=[
      ("RESISTOR",420,265,1),("AMMETER",420,330,1),("DC_POWER",420,395,0),("SPST",420,455,1),
      ("RESISTOR",610,300,1),("AMMETER",610,385,1),
      ("RESISTOR",800,265,1),("AMMETER",800,330,1),("DC_POWER",800,395,0),("SPST",800,455,1),
      ("VOLTMETER",900,350,1),("GROUND",610,505,0)
    ]
    for it in items:
        if not place(*it):
            log(f"FAILED placement {it}");return 20
    shot("20_all_components.png")

    # Set required values. We accept unit-bearing strings in Multisim property dialog.
    set_value(420,265,"100 Ohm")
    set_value(610,300,"200 Ohm")
    set_value(800,265,"150 Ohm")
    set_value(420,395,"10 V")
    set_value(800,395,"15 V")
    shot("30_values_set.png")

    # Wiring, using centers and vertical terminal offsets after rotation.
    # common top bus c and bottom bus a
    wire([(360,220),(860,220)])
    wire([(360,500),(860,500)])
    # left branch segments
    wire([(420,220),(420,245)])
    wire([(420,285),(420,310)])
    wire([(420,350),(420,375)])
    wire([(420,415),(420,435)])
    wire([(420,475),(420,500)])
    # middle branch
    wire([(610,220),(610,280)])
    wire([(610,320),(610,365)])
    wire([(610,405),(610,500)])
    # right branch
    wire([(800,220),(800,245)])
    wire([(800,285),(800,310)])
    wire([(800,350),(800,375)])
    wire([(800,415),(800,435)])
    wire([(800,475),(800,500)])
    # voltmeter across nodes
    wire([(860,220),(900,220),(900,330)])
    wire([(900,370),(900,500),(860,500)])
    # ground lead
    wire([(610,500),(610,495)])
    shot("40_wired.png")

    # Close both switches by clicking their levers.
    pyautogui.click(420,455);time.sleep(.5);pyautogui.click(800,455);time.sleep(.5)
    shot("45_switches_closed.png")

    if not save_as():
        log("save failed");return 21
    log(f"saved {TARGET} size={TARGET.stat().st_size}")
    shot("50_saved.png")

    if not reopen_in_app():
        log("reopen verification failed");return 22

    focus();pyautogui.press("f5");time.sleep(7);shot("70_run.png")
    pyautogui.press("f5");time.sleep(1)
    log("LAB2_NATIVE_DONE")
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except Exception:
        log(traceback.format_exc());shot("99_exception.png");sys.exit(99)
