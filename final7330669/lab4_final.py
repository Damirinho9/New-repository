import os, sys, time, subprocess, traceback, re
from pathlib import Path

MULTISIM=Path(sys.argv[1]); OUT=Path(sys.argv[2])
OUT.mkdir(parents=True,exist_ok=True)
TARGET=OUT/"Lab4_Diodes.ms14"
LOG=OUT/"lab4-final.log"
DY=0

def P(x,y):
    return (x,y+DY)

def calibrate_viewport(tag):
    global DY
    import pyautogui
    im=pyautogui.screenshot().convert("RGB")
    best=(-1,-1)
    for yy in range(185,285):
        run=mx=0
        for xx in range(370,451):
            r,g,b=im.getpixel((xx,yy))
            blue=(b>150 and r<100 and g<180)
            if blue:
                run+=1
                if run>mx:mx=run
            else:
                run=0
        if mx>best[0]:
            best=(mx,yy)
    if best[0] < 8:
        log(f"viewport calibration failed tag={tag} best={best}")
        return False
    DY=best[1]-209
    log(f"viewport tag={tag} switch_pin_y={best[1]} DY={DY} run={best[0]}")
    return True


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

    # Prefer real Multisim property dialogs. Never accept Terminal or the main Multisim frame.
    for backend in ("uia","win32"):
        try:
            wins=Desktop(backend=backend).windows()
            for d in wins:
                try:
                    title=d.window_text().strip()
                    cls=d.class_name()
                    r=d.rectangle()
                    if r.width()<200 or r.height()<100:continue
                    if "Multisim" in title or "GitHub" in title or "HostedComputeAgent" in title:continue
                    # Component property dialogs expose Value/Label/Fault tabs or have the native #32770 class.
                    texts=[]
                    try:
                        for e in d.descendants():
                            try:
                                t=e.window_text().strip()
                                if t:texts.append(t)
                            except:pass
                    except:pass
                    tabset=set(texts)
                    looks_prop=("Value" in tabset and ("Label" in tabset or "Fault" in tabset)) or (cls=="#32770" and any(x in title.upper() for x in ("RESISTOR","POWER","AMMETER","VOLTMETER","SPST")))
                    if looks_prop:
                        log(f"property dialog title={title!r} class={cls} rect={r}")
                        try:d.set_focus()
                        except:pass
                        return d
                except:pass
        except:pass

    # Last fallback: foreground only if it is a native dialog and not a terminal/main window.
    hwnd=win32gui.GetForegroundWindow()
    for backend in ("uia","win32"):
        try:
            d=Desktop(backend=backend).window(handle=hwnd)
            title=d.window_text().strip();cls=d.class_name();r=d.rectangle()
            log(f"foreground fallback title={title!r} class={cls} rect={r}")
            if cls=="#32770" and "Multisim" not in title and "GitHub" not in title and r.width()>200 and r.height()>100:
                return d
        except:pass
    return None

def set_value(x,y,value,unit_hint=None):
    import pyautogui
    focus();pyautogui.doubleClick(x,y,interval=.15);time.sleep(1.5)
    d=modal_dialog()
    if not d:
        log(f"value dialog missing first try at {x},{y}; retrying")
        pyautogui.press("esc");focus();time.sleep(.5)
        pyautogui.doubleClick(x,y,interval=.15);time.sleep(1.5)
        d=modal_dialog()
    if not d:
        log(f"value dialog missing after retry at {x},{y}");pyautogui.press("esc");return False
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

        # Work only inside the visible Value pane, not hidden Fault/Label controls.
        value_pane=None
        for e in d.descendants():
            try:
                if e.window_text().strip()=="Value" and e.class_name()=="#32770":
                    value_pane=e;break
            except:pass
        scope=value_pane.descendants() if value_pane else d.descendants()

        edits=[];statics=[]
        for e in scope:
            try:
                ct=getattr(e.element_info,"control_type","")
                r=e.rectangle();cur=e.window_text()
                if (ct=="Edit" or "Edit" in e.class_name()) and r.width()>25 and r.height()>10:
                    edits.append((e,cur,r))
                if ct=="Text" or e.class_name()=="Static":
                    statics.append((e,cur,r))
            except:pass

        chosen=None
        # Select the Edit field on the same row as the requested unit label.
        if unit_hint:
            unit_rows=[]
            for _,cur,r in statics:
                norm=cur.strip().replace("Ω","OHM")
                if norm==unit_hint:
                    unit_rows.append((r.top+r.bottom)//2)
            unit_rows.sort()
            if unit_rows:
                target_y=unit_rows[0]
                candidates=[]
                for e,cur,r in edits:
                    cy=(r.top+r.bottom)//2
                    if abs(cy-target_y)<=4:
                        candidates.append((abs(cy-target_y),-r.width(),e,cur,r))
                if candidates:
                    candidates.sort(key=lambda z:(z[0],z[1]))
                    chosen=candidates[0][2]
                    log(f"value field by unit {unit_hint}: current={candidates[0][3]!r} rect={candidates[0][4]}")

        if chosen is None and edits:
            edits.sort(key=lambda z:z[2].top)
            chosen=edits[0][0]
            log(f"value field fallback current={edits[0][1]!r} rect={edits[0][2]}")

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
    a=P(*a); b=P(*b)
    a=find_hotspot(*a,radius=2); b=find_hotspot(*b,radius=2)
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

def wire_path(points):
    import pyautogui
    if not WIRE_STRATEGY or len(points)<2:return False
    pts=[P(*p) for p in points]
    pts[0]=find_hotspot(*pts[0],radius=2)
    pts[-1]=find_hotspot(*pts[-1],radius=2)
    focus()
    log(f"wire_path strategy={WIRE_STRATEGY} pts={pts}")
    try:
        if WIRE_STRATEGY=="click":
            pyautogui.moveTo(*pts[0],duration=.1);pyautogui.click();time.sleep(.3)
            for p in pts[1:]:
                pyautogui.moveTo(*p,duration=.15);pyautogui.click();time.sleep(.25)
            pyautogui.press("esc")
        elif WIRE_STRATEGY=="menu":
            w=focus()
            try:w.menu_select("Place->Wire")
            except:
                pyautogui.hotkey("alt","p");time.sleep(.3);pyautogui.press("w")
            time.sleep(.3)
            for p in pts:
                pyautogui.click(*p);time.sleep(.25)
            pyautogui.press("esc")
        elif WIRE_STRATEGY=="ctrlq":
            pyautogui.hotkey("ctrl","q");time.sleep(.3)
            for p in pts:
                pyautogui.click(*p);time.sleep(.25)
            pyautogui.press("esc")
        else:
            # drag is unsuitable for bent buses; use plain clicks which match Multisim manual wiring.
            pyautogui.moveTo(*pts[0],duration=.1);pyautogui.click();time.sleep(.3)
            for p in pts[1:]:
                pyautogui.moveTo(*p,duration=.15);pyautogui.click();time.sleep(.25)
            pyautogui.press("esc")
        time.sleep(.6)
        return True
    except Exception as e:
        log(f"wire_path exception {e}")
        pyautogui.press("esc")
        return False

def junction(x,y):
    import pyautogui
    x,y=P(x,y)
    focus();pyautogui.hotkey("ctrl","j");time.sleep(.25);pyautogui.click(x,y);pyautogui.press("esc");time.sleep(.3)
    log(f"junction at {x},{y}")

def simulation_messages():
    vals=[]
    w=mainwin()
    if not w:return vals
    for backend in ("uia","win32"):
        try:
            from pywinauto import Desktop
            q=Desktop(backend=backend).window(handle=w.handle)
            for e in q.descendants():
                try:
                    t=e.window_text().strip()
                    if t and ("Warning:" in t or "error(s)" in t or "warning(s)" in t or "SPICE Netlist" in t):
                        vals.append(t)
                except:pass
        except:pass
    return sorted(set(vals))

def run_and_capture(name):
    import pyautogui
    focus();pyautogui.press("f5");time.sleep(6)
    shot(name)
    msgs=simulation_messages()
    log("simulation messages="+" || ".join(msgs))
    bad=[m for m in msgs if ("No ground node" in m or re.search(r"\\b[1-9]\\d* error\\(s\\)",m,re.I))]
    pyautogui.press("f5");time.sleep(1)
    return bad

def save_as():
    import pyautogui
    from pywinauto import Desktop
    focus()
    try:
        focus().menu_select("File->Save As...")
    except:
        pyautogui.hotkey("ctrl","shift","s")
    time.sleep(2)
    d=None
    for _ in range(20):
        for backend in ("win32","uia"):
            try:
                for q in Desktop(backend=backend).windows():
                    try:
                        r=q.rectangle(); cls=q.class_name(); t=q.window_text()
                    except: continue
                    if cls=="#32770" and r.width()>500 and r.height()>250 and "Select a Component" not in t:
                        d=q; break
                if d: break
            except: pass
        if d: break
        time.sleep(.3)
    if not d:
        log("save dialog missing"); shot("49_save_dialog_missing.png"); return False
    try: d.set_focus()
    except: pass
    pyautogui.hotkey("alt","n"); time.sleep(.3)
    pyautogui.hotkey("ctrl","a"); pyautogui.write(str(TARGET),interval=.002)
    pyautogui.press("enter"); time.sleep(7); pyautogui.press("enter"); time.sleep(2)
    cand=list(OUT.glob("*.ms14"))
    if TARGET.exists(): return TARGET.stat().st_size>1000
    for p in cand:
        if p.stat().st_size>1000:
            p.replace(TARGET); return True
    return False

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
    return ("Lab4_Diodes".lower() in title.lower()) or TARGET.exists()


def blue_pin(cx,cy,side,rx=85,ry=45):
    import pyautogui
    im=pyautogui.screenshot().convert("RGB")
    x0=max(0,int(cx-rx));x1=min(im.width,int(cx+rx))
    y0=max(0,int(cy-ry));y1=min(im.height,int(cy+ry))
    pts=set()
    for yy in range(y0,y1):
        for xx in range(x0,x1):
            r,g,b=im.getpixel((xx,yy))
            if b>145 and r<105 and g<190:
                pts.add((xx,yy))
    comps=[]
    while pts:
        seed=pts.pop();stack=[seed];comp=[seed]
        while stack:
            x,y=stack.pop()
            for nx in (x-1,x,x+1):
                for ny in (y-1,y,y+1):
                    q=(nx,ny)
                    if q in pts:
                        pts.remove(q);stack.append(q);comp.append(q)
        xs=[p[0] for p in comp];ys=[p[1] for p in comp]
        w=max(xs)-min(xs)+1;h=max(ys)-min(ys)+1
        if 2<=len(comp)<=80 and w<=14 and h<=14:
            comps.append((sum(xs)/len(xs),sum(ys)/len(ys),len(comp),w,h))
    if not comps:
        log(f"blue_pin none around {cx},{cy} side={side}")
        return (int(cx),int(cy))
    if side=="left": q=min(comps,key=lambda p:p[0])
    elif side=="right": q=max(comps,key=lambda p:p[0])
    elif side=="top": q=min(comps,key=lambda p:p[1])
    else: q=max(comps,key=lambda p:p[1])
    p=(int(round(q[0])),int(round(q[1])))
    log(f"blue_pin {side} around {cx},{cy} -> {p}")
    return p

def direct_path(points):
    import pyautogui
    focus()
    pyautogui.moveTo(*points[0],duration=.1);pyautogui.click();time.sleep(.25)
    for p in points[1:]:
        pyautogui.moveTo(*p,duration=.12);pyautogui.click();time.sleep(.2)
    pyautogui.press("esc");time.sleep(.35)
    return True


def cursor_pin(cx,cy,side,rx=70,ry=30):
    import win32api, win32gui, time
    focus()
    win32api.SetCursorPos((900,575)); time.sleep(.05)
    base=win32gui.GetCursorInfo()[1]
    candidates=[]
    x0=max(260,int(cx-rx)); x1=min(950,int(cx+rx))
    y0=max(165,int(cy-ry)); y1=min(540,int(cy+ry))
    for yy in range(y0,y1+1,2):
        for xx in range(x0,x1+1,2):
            win32api.SetCursorPos((xx,yy))
            h=win32gui.GetCursorInfo()[1]
            if h!=base:
                candidates.append((xx,yy,h))
    if not candidates:
        log(f"cursor_pin fallback {side} around {cx},{cy}")
        return (int(cx),int(cy))
    if side=="left": q=min(candidates,key=lambda p:p[0])
    elif side=="right": q=max(candidates,key=lambda p:p[0])
    elif side=="top": q=min(candidates,key=lambda p:p[1])
    else: q=max(candidates,key=lambda p:p[1])
    p=(q[0],q[1])
    log(f"cursor_pin {side} around {cx},{cy} -> {p} handle={q[2]} base={base}")
    return p

def direct_path2(points):
    import pyautogui
    focus()
    pyautogui.moveTo(*points[0],duration=.1); pyautogui.click(); time.sleep(.25)
    for p in points[1:]:
        pyautogui.moveTo(*p,duration=.12); pyautogui.click(); time.sleep(.2)
    pyautogui.press("esc"); time.sleep(.35)
    return True

def main():
    import pyautogui
    global DY
    pyautogui.FAILSAFE=False
    p=subprocess.Popen([str(MULTISIM)]); log(f"launch pid={p.pid}"); time.sleep(10)
    if trial_present() and not dismiss_trial(): return 11
    if not focus(): return 12
    DY=24

    # Universal measurement circuit from Fig. 4.6. The tested device is 1N4001;
    # 1N4728 and green LED use the same circuit by replacing only the DUT.
    items=[
      ("DC_POWER",430,245,1),
      ("AMMETER",530,245,0),
      ("1N4001",690,245,0),
      ("VOLTMETER",690,305,0),
      ("GROUND",350,320,0)
    ]
    for it in items:
        if not place(*it): return 20
    shot("10_components.png")

    if not set_value(*P(449,199),"0.7","V"): return 21
    shot("20_values.png")

    # Pin locations are stable on the default Multisim sheet; refine each by cursor hotspot.
    srcL=find_hotspot(435,200,8); srcR=find_hotspot(468,200,8)
    amL=find_hotspot(541,200,8); amR=find_hotspot(623,200,8)
    dL=find_hotspot(700,200,10); dR=find_hotspot(748,200,10)
    vL=find_hotspot(702,255,10); vR=find_hotspot(782,255,10)
    gT=find_hotspot(350,320,14)

    direct_path2([srcR,amL])
    direct_path2([amR,dL])
    direct_path2([dR,(800,200),(800,300),(330,300),(330,200),srcL])
    direct_path2([gT,(350,300),(330,300)])
    direct_path2([dL,(660,255),vL])
    direct_path2([dR,(790,255),vR])
    shot("30_wired.png")

    if not save_as(): return 22
    shot("40_saved.png")
    if not reopen_in_app(): return 23

    focus(); pyautogui.press("f5"); time.sleep(6)
    shot("60_reopened_run_1N4001.png")
    msgs=simulation_messages(); log("Lab4 messages="+" || ".join(msgs))
    bad=[m for m in msgs if ("No ground node" in m or re.search(r"\\b[1-9]\\d* error\\(s\\)",m,re.I))]
    pyautogui.press("f5"); time.sleep(1)
    if bad: return 24

    focus(); pyautogui.hotkey("ctrl","s"); time.sleep(2)
    log("LAB4_NATIVE_DONE")
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except Exception:
        log(traceback.format_exc());shot("99_exception.png");sys.exit(99)
