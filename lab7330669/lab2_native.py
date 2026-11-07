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
    import win32gui
    from pywinauto import Desktop
    time.sleep(.8)
    hwnd=win32gui.GetForegroundWindow()
    try:
        d=Desktop(backend="uia").window(handle=hwnd)
        r=d.rectangle()
        log(f"foreground dialog title={d.window_text()!r} class={d.class_name()} rect={r}")
        if r.width()>200 and r.height()>100:return d
    except Exception as e:
        log(f"foreground UIA failed {e}")
    try:
        d=Desktop(backend="win32").window(handle=hwnd)
        r=d.rectangle()
        if r.width()>200 and r.height()>100:return d
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
        edits.sort(key=lambda z:z[3].top)
        title=d.window_text().upper()
        if "RESISTOR" in title and len(edits)>=2:
            chosen=edits[1][1]
        else:
            chosen=edits[0][1] if edits else None
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

def find_hotspot(x,y,radius=5):
    import pyautogui, win32gui
    # Cursor over blank grid is the baseline. A component terminal changes it.
    pyautogui.moveTo(900,575,duration=.02);time.sleep(.08)
    try:base=win32gui.GetCursorInfo()[1]
    except:return (x,y)
    cand=[]
    for rr in range(radius+1):
        for dx in range(-rr,rr+1):
            for dy in (-rr,rr):
                xx,yy=x+dx,y+dy
                pyautogui.moveTo(xx,yy,duration=.005);time.sleep(.01)
                try:h=win32gui.GetCursorInfo()[1]
                except:h=base
                if h!=base:cand.append((abs(dx)+abs(dy),xx,yy,h))
        for dy in range(-rr+1,rr):
            for dx in (-rr,rr):
                xx,yy=x+dx,y+dy
                pyautogui.moveTo(xx,yy,duration=.005);time.sleep(.01)
                try:h=win32gui.GetCursorInfo()[1]
                except:h=base
                if h!=base:cand.append((abs(dx)+abs(dy),xx,yy,h))
        if cand:break
    if cand:
        cand.sort()
        _,px,py,h=cand[0]
        log(f"hotspot ({x},{y})->({px},{py}) cursor={h} baseline={base}")
        return (px,py)
    log(f"hotspot fallback ({x},{y})")
    return (x,y)

def _wire_diff(before,after,a,b):
    from PIL import ImageChops,ImageStat
    x1=min(a[0],b[0])-4; x2=max(a[0],b[0])+5
    y1=min(a[1],b[1])-4; y2=max(a[1],b[1])+5
    box=(max(0,x1),max(0,y1),min(before.width,x2),min(before.height,y2))
    d=ImageChops.difference(before.crop(box),after.crop(box))
    st=ImageStat.Stat(d)
    score=sum(st.sum)
    log(f"wire diff box={box} score={score:.0f}")
    return score

def _clean_after_failed_wire():
    import pyautogui
    pyautogui.press("esc", presses=2, interval=.1)
    pyautogui.hotkey("ctrl","z")
    time.sleep(.5)

def try_wire_strategy(strategy,a,b,test=False):
    import pyautogui
    a=find_hotspot(*a); b=find_hotspot(*b)
    focus();pyautogui.moveTo(900,575);time.sleep(.2)
    before=pyautogui.screenshot() if test else None
    log(f"wire strategy={strategy} a={a} b={b}")
    try:
        if strategy=="click":
            pyautogui.moveTo(*a,duration=.1);pyautogui.click();time.sleep(.4)
            pyautogui.moveTo(*b,duration=.2);pyautogui.click();time.sleep(.4)
            pyautogui.press("esc")
        elif strategy=="drag":
            pyautogui.moveTo(*a,duration=.1);pyautogui.dragTo(*b,duration=.7,button="left");time.sleep(.4)
            pyautogui.press("esc")
        elif strategy=="menu":
            w=focus()
            try:w.menu_select("Place->Wire")
            except:
                pyautogui.hotkey("alt","p");time.sleep(.3);pyautogui.press("w")
            time.sleep(.4);pyautogui.click(*a);time.sleep(.3);pyautogui.click(*b);pyautogui.press("esc")
        elif strategy=="ctrlq":
            pyautogui.hotkey("ctrl","q");time.sleep(.3);pyautogui.click(*a);time.sleep(.3);pyautogui.click(*b);pyautogui.press("esc")
        else:return False
        time.sleep(.7);pyautogui.moveTo(900,575);time.sleep(.2)
        if not test:return True
        after=pyautogui.screenshot()
        score=_wire_diff(before,after,a,b)
        # A real wire changes a substantial number of pixels even for a short 25 px gap.
        return score>4500
    except Exception as e:
        log(f"wire strategy {strategy} exception {e}")
        return False

WIRE_STRATEGY=None

def calibrate_wire_strategy():
    global WIRE_STRATEGY
    # Short isolated gap between S1 right pin and V1 left pin is ideal for visual validation.
    a=(442,209);b=(469,209)
    for st in ("click","drag","menu","ctrlq"):
        ok=try_wire_strategy(st,a,b,test=True)
        shot(f"35_wiretest_{st}.png")
        if ok:
            WIRE_STRATEGY=st
            log(f"WIRE_STRATEGY_SELECTED={st}")
            return True
        _clean_after_failed_wire()
    log("NO_WIRE_STRATEGY_WORKED")
    return False

def wire(a,b):
    if not WIRE_STRATEGY:return False
    return try_wire_strategy(WIRE_STRATEGY,a,b,test=False)

def junction(x,y):
    import pyautogui
    focus();pyautogui.hotkey("ctrl","j");time.sleep(.25);pyautogui.click(x,y);pyautogui.press("esc");time.sleep(.3)
    log(f"junction at {x},{y}")

def warning_windows():
    from pywinauto import Desktop
    vals=[]
    for backend in ("win32","uia"):
        try:
            for w in Desktop(backend=backend).windows():
                try:
                    t=w.window_text().strip()
                    if t and ("warning" in t.lower() or "error" in t.lower()):
                        vals.append(t)
                except:pass
        except:pass
    return sorted(set(vals))

def run_and_capture(name):
    import pyautogui
    focus();pyautogui.press("f5");time.sleep(6)
    shot(name)
    warns=warning_windows()
    log(f"run warnings={warns}")
    # close modal warning if one exists
    if warns:
        pyautogui.press("enter");time.sleep(1)
    else:
        pyautogui.press("f5");time.sleep(1)
    return warns

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
    focus();pyautogui.hotkey("ctrl","f4");time.sleep(4);pyautogui.press("esc");time.sleep(2)
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
    # Native Windows file dialog: Alt+N focuses "File name".
    pyautogui.hotkey("alt","n");time.sleep(.4)
    pyautogui.hotkey("ctrl","a");pyautogui.write(str(TARGET),interval=.002)
    pyautogui.press("enter");time.sleep(12)
    w=focus();title=w.window_text() if w else ""
    log(f"reopened title={title!r}")
    shot("60_reopened.png")
    return ("Lab2_DC_Circuit".lower() in title.lower()) or TARGET.exists()

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
      ("VOLTMETER",570,535,0),("GROUND",340,500,0)
    ]
    for it in items:
        if not place(*it):
            log(f"FAILED placement {it}");return 20
    shot("20_all_components.png")

    # Required values from the method sheet.
    okvals=[
      set_value(725,209,"100"),
      set_value(675,299,"200"),
      set_value(725,398,"150"),
      set_value(489,209,"10"),
      set_value(463,398,"15")
    ]
    shot("30_values_set.png")
    if not all(okvals):
        log("one or more values could not be set");return 24

    # Find one native wiring method once, then reuse it for the whole circuit.
    if not calibrate_wire_strategy():
        return 25

    # Short serial gaps in the three branches. The S1-V1 wire was already created by calibration.
    for a,b in [
        ((505,209),(568,209)),((667,209),(703,209)),
        ((595,299),(649,299)),
        ((442,398),(469,398)),((505,398),(568,398)),((667,398),(703,398))
    ]:
        wire(a,b)

    # Explicit node junctions eliminate dependence on clicking an existing wire.
    A=(330,330); C=(790,330)
    junction(*A); junction(*C)

    # Node a: switch inputs, central ammeter input, voltmeter left terminal and ground.
    for p in [(379,209),(496,299),(379,398),(568,489),(342,479)]:
        wire(p,A)

    # Node c: resistor outputs and voltmeter right terminal.
    for p in [(748,209),(694,299),(748,398),(667,489)]:
        wire(p,C)

    shot("40_wired.png")

    # Close K1 and K2.
    pyautogui.click(410,209);time.sleep(.5)
    pyautogui.click(410,398);time.sleep(.5)
    shot("45_switches_closed.png")

    if not save_as():
        log("save failed");return 21
    log(f"saved {TARGET} size={TARGET.stat().st_size}")
    shot("50_saved.png")

    if not reopen_in_app():
        log("reopen verification failed");return 22

    # State 1: original circuit, K1/K2 closed.
    warns=run_and_capture("70_run_initial.png")
    if warns:
        # One last in-run repair: connect ground directly to node-a junction and retry.
        log("initial run produced warning; reinforcing ground connection without reinstall")
        wire((342,479),(330,330))
        warns=run_and_capture("71_run_ground_retry.png")
        if warns:return 26

    # State 2: open branch c-a (remove the short wire between U2 and R3), measure Uxx.
    # Selecting the midpoint of that wire and Delete is reversible with Ctrl+Z.
    pyautogui.click(622,299);pyautogui.press("delete");time.sleep(1)
    run_and_capture("80_state_Uxx_open_R3.png")
    pyautogui.hotkey("ctrl","z");time.sleep(1)

    # State 3: short R3 by bypassing it from U2 output directly to node c.
    wire((595,299),(790,330))
    run_and_capture("90_state_Ikz_R3_short.png")
    pyautogui.hotkey("ctrl","z");time.sleep(1)

    # Return to original state and save it as the submitted MS14.
    focus();pyautogui.hotkey("ctrl","s");time.sleep(3)
    shot("95_final_original_state.png")
    log("LAB2_NATIVE_DONE")
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except Exception:
        log(traceback.format_exc());shot("99_exception.png");sys.exit(99)
