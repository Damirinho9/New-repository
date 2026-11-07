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
    from pywinauto import Desktop, Application
    mw=focus()
    if not mw:return None
    pid=mw.process_id()
    # Prefer visible secondary windows belonging to the Multisim process.
    for backend in ("uia","win32"):
        try:
            app=Application(backend=backend).connect(process=pid)
            for w in app.windows():
                try:
                    if w.handle != mw.handle and w.is_visible():
                        r=w.rectangle()
                        if r.width()>250 and r.height()>120:
                            log(f"property window backend={backend} title={w.window_text()!r} class={w.class_name()} rect={r}")
                            return w
                except:pass
        except:pass
    # Fallback to process-scoped #32770 dialogs.
    try:
        for w in Desktop(backend="win32").windows(process=pid):
            try:
                if w.handle != mw.handle and w.class_name()=="#32770":
                    return w
            except:pass
    except:pass
    return None

def set_value(x,y,value):
    import pyautogui
    focus();pyautogui.doubleClick(x,y,interval=.15);time.sleep(1.5)
    d=modal_dialog()
    if not d:
        log(f"value dialog missing at {x},{y}");pyautogui.press("esc");return False
    try:
        # Dump controls for diagnostics.
        vals=[]
        for e in d.descendants():
            try:
                vals.append(f"{e.window_text()!r}\t{e.class_name()}\t{getattr(e.element_info,'control_type','')}\t{e.rectangle()}")
            except:pass
        with (OUT/f"prop_{x}_{y}.txt").open("w",encoding="utf-8") as fh:fh.write("\n".join(vals))

        for e in d.descendants():
            try:
                if e.window_text().strip()=="Value" and e.rectangle().width()>5:
                    e.click_input();time.sleep(.5);break
            except:pass

        edits=[]
        for e in d.descendants():
            try:
                ct=getattr(e.element_info,"control_type","")
                if ct=="Edit" or "Edit" in e.class_name():
                    r=e.rectangle();cur=e.window_text()
                    if r.width()>25 and r.height()>10:edits.append((r.width()*r.height(),e,cur,r))
            except:pass
        edits.sort(reverse=True,key=lambda z:z[0])
        log("property edits: "+" | ".join([f"{q[2]!r}@{q[3]}" for q in edits[:10]]))
        chosen=None
        for _,e,cur,r in edits:
            u=cur.strip()
            if re.search(r"\d",u) and not re.fullmatch(r"[A-Za-z]+\d+",u):
                chosen=e;break
        if chosen is None and edits:chosen=edits[-1][1]
        if chosen is None:
            pyautogui.press("esc");return False
        try:chosen.set_edit_text(value)
        except:
            chosen.click_input();pyautogui.hotkey("ctrl","a");pyautogui.write(value,interval=.04)
        time.sleep(.5)
        # Click OK if available.
        clicked=False
        for b in d.descendants():
            try:
                if b.window_text().replace("&","").strip()=="OK" and b.rectangle().width()>5:
                    b.click_input();clicked=True;break
            except:pass
        if not clicked:pyautogui.press("enter")
        time.sleep(1)
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
    focus();pyautogui.hotkey("ctrl","s");time.sleep(2)
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

    # Figure 2.6 topology, laid out as three horizontal branches for reliable native GUI wiring.
    # Common node a is the left bus, node c is the right bus.
    items=[
      ("SPST",380,255,0),("DC_POWER",470,255,1),("AMMETER",570,255,0),("RESISTOR",700,255,0),
      ("AMMETER",500,350,0),("RESISTOR",650,350,0),
      ("SPST",380,445,0),("DC_POWER",470,445,3),("AMMETER",570,445,2),("RESISTOR",700,445,0),
      ("VOLTMETER",570,535,0),("GROUND",320,570,0)
    ]
    for it in items:
        if not place(*it):
            log(f"FAILED placement {it}");return 20
    shot("20_all_components.png")

    # Required values from the method sheet.
    okvals=[
      set_value(700,255,"100 Ohm"),
      set_value(650,350,"200 Ohm"),
      set_value(700,445,"150 Ohm"),
      set_value(470,255,"10 V"),
      set_value(470,445,"15 V")
    ]
    shot("30_values_set.png")
    if not all(okvals):
        log("one or more values could not be set");return 24

    # Exact horizontal wiring using the terminal geometry of native Multisim 14.3 components.
    # left/right common buses
    wire([(320,230),(320,535)])
    wire([(830,230),(830,535)])
    # branch 1: K1 - E1 - A1 - R1
    wire([(320,255),(348,255)])
    wire([(412,255),(450,255)])
    wire([(490,255),(528,255)])
    wire([(612,255),(677,255)])
    wire([(723,255),(830,255)])
    # branch 3: A3 - R3
    wire([(320,350),(458,350)])
    wire([(542,350),(627,350)])
    wire([(673,350),(830,350)])
    # branch 2: K2 - E2 - A2 - R2
    wire([(320,445),(348,445)])
    wire([(412,445),(450,445)])
    wire([(490,445),(528,445)])
    wire([(612,445),(677,445)])
    wire([(723,445),(830,445)])
    # voltmeter across a-c
    wire([(320,535),(528,535)])
    wire([(612,535),(830,535)])
    # ground on node a
    wire([(320,535),(320,560)])
    shot("40_wired.png")

    # Close K1 and K2.
    pyautogui.click(380,255);time.sleep(.5)
    pyautogui.click(380,445);time.sleep(.5)
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
