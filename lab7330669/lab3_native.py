import sys,time,subprocess,traceback,re
from pathlib import Path
MULTISIM=Path(sys.argv[1]); OUT=Path(sys.argv[2]); OUT.mkdir(parents=True,exist_ok=True)
TARGET=OUT/"Lab3_Current_Resonance.ms14"; LOG=OUT/"lab3-native.log"

def log(m):
    s=f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {m}"; print(s,flush=True)
    with LOG.open("a",encoding="utf-8") as f:f.write(s+"\n")

def shot(n):
    import pyautogui
    p=OUT/n; pyautogui.screenshot(str(p)); log(f"screenshot={p}")

def mainwin():
    from pywinauto import Desktop
    ws=[]
    for w in Desktop(backend="win32").windows():
        try:
            if "Multisim" in w.window_text() and "Select a Component" not in w.window_text(): ws.append(w)
        except: pass
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

def dismiss_trial():
    import pyautogui
    from pywinauto import Desktop
    for _ in range(3):
        for backend in ("uia","win32"):
            try:
                for w in Desktop(backend=backend).windows():
                    for d in w.descendants():
                        try:t=d.window_text();r=d.rectangle()
                        except:continue
                        if ("Trial" in t or "Extend Trial" in t) and r.width()>5 and r.height()>5:
                            try:d.click_input();time.sleep(4)
                            except:pass
            except:pass
    pyautogui.press("esc"); return True

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
        time.sleep(.3)
    return None

def place(name,x,y,rotate=0):
    import pyautogui
    d=comp_dialog()
    if not d: log("component dialog missing "+name);return False
    r=d.rectangle()
    pyautogui.click(r.left+300,r.top+65);pyautogui.hotkey("ctrl","a");pyautogui.write(name,interval=.03);time.sleep(1.2)
    pyautogui.click(r.left+310,r.top+89);time.sleep(.3)
    pyautogui.click(r.right-50,r.top+50);time.sleep(1)
    for _ in range(rotate):pyautogui.hotkey("ctrl","r");time.sleep(.25)
    pyautogui.click(x,y);time.sleep(.6);pyautogui.press("esc");time.sleep(.4)
    log(f"placed {name} {x},{y} rot={rotate}");return True

def modal_dialog():
    import win32gui
    from pywinauto import Desktop
    time.sleep(.8);hwnd=win32gui.GetForegroundWindow()
    for backend in ("uia","win32"):
        try:
            d=Desktop(backend=backend).window(handle=hwnd);r=d.rectangle()
            if r.width()>200 and r.height()>100:return d
        except:pass
    return None

def property_edits(x,y):
    import pyautogui
    focus();pyautogui.doubleClick(x,y,interval=.12);time.sleep(1.2)
    d=modal_dialog()
    if not d:return None,[]
    edits=[]
    for e in d.descendants():
        try:
            ct=getattr(e.element_info,"control_type","")
            if ct=="Edit" or "Edit" in e.class_name():
                r=e.rectangle()
                if r.width()>25 and r.height()>10: edits.append((r.top,r.left,e,e.window_text()))
        except:pass
    edits.sort()
    return d,edits

def close_prop(d):
    import pyautogui
    for b in d.descendants():
        try:
            if b.window_text().replace("&","").strip()=="OK" and b.rectangle().width()>5:
                b.click_input();time.sleep(.8);return
        except:pass
    pyautogui.press("enter");time.sleep(.8)

def set_passive(x,y,val):
    import pyautogui
    d,edits=property_edits(x,y)
    if not d or not edits:return False
    title=d.window_text().upper()
    # passive part dialogs generally have refdes first, value second
    e=edits[1][2] if len(edits)>1 else edits[0][2]
    try:e.set_edit_text(str(val))
    except:
        e.click_input();pyautogui.hotkey("ctrl","a");pyautogui.write(str(val))
    close_prop(d);log(f"passive {title}={val}");return True

def set_ac_source(x,y,voltage="220",freq="50"):
    import pyautogui
    d,edits=property_edits(x,y)
    if not d or len(edits)<2:return False
    # Ignore a RefDes-like edit if present; choose numeric fields by current text.
    num=[]
    for _,_,e,t in edits:
        if re.search(r"\d",t or "") and not re.fullmatch(r"[A-Za-z]+\d+",(t or "").strip()):
            num.append(e)
    if len(num)<2:num=[z[2] for z in edits[-3:]]
    try:num[0].set_edit_text(voltage)
    except:num[0].click_input();pyautogui.hotkey("ctrl","a");pyautogui.write(voltage)
    try:num[1].set_edit_text(freq)
    except:num[1].click_input();pyautogui.hotkey("ctrl","a");pyautogui.write(freq)
    close_prop(d);log(f"AC source V={voltage} f={freq}");return True

def find_terminal(cx,cy,side):
    import pyautogui,win32gui
    pyautogui.moveTo(1000,600);time.sleep(.05)
    try:base=win32gui.GetCursorInfo()[1]
    except:return (cx,cy)
    pts=[]
    for yy in range(cy-65,cy+66,3):
        for xx in range(cx-65,cx+66,3):
            pyautogui.moveTo(xx,yy,duration=.001);time.sleep(.003)
            try:h=win32gui.GetCursorInfo()[1]
            except:h=base
            if h!=base:pts.append((xx,yy))
    if not pts:return (cx,cy)
    if side=="top": p=min(pts,key=lambda z:z[1])
    elif side=="bottom":p=max(pts,key=lambda z:z[1])
    elif side=="left":p=min(pts,key=lambda z:z[0])
    else:p=max(pts,key=lambda z:z[0])
    log(f"terminal {side} around {cx},{cy} -> {p}");return p

def wire_path(points):
    import pyautogui
    focus()
    pyautogui.moveTo(*points[0]);pyautogui.click();time.sleep(.25)
    for p in points[1:]:
        pyautogui.moveTo(*p,duration=.12);pyautogui.click();time.sleep(.2)
    pyautogui.press("esc");time.sleep(.35)

def save_as():
    import pyautogui
    from pywinauto import Desktop
    focus()
    try:focus().menu_select("File->Save As...")
    except:pyautogui.hotkey("ctrl","shift","s")
    time.sleep(2)
    d=None
    for _ in range(15):
        for backend in ("win32","uia"):
            try:
                for q in Desktop(backend=backend).windows():
                    try:r=q.rectangle();cls=q.class_name();t=q.window_text()
                    except:continue
                    if cls=="#32770" and r.width()>500 and r.height()>250 and "Select a Component" not in t:
                        d=q;break
                if d:break
            except:pass
        if d:break
        time.sleep(.3)
    if not d:return False
    try:d.set_focus()
    except:pass
    pyautogui.hotkey("alt","n");time.sleep(.3);pyautogui.hotkey("ctrl","a");pyautogui.write(str(TARGET),interval=.002);pyautogui.press("enter")
    time.sleep(6);pyautogui.press("enter");time.sleep(2)
    cand=list(OUT.glob("*.ms14"))
    if TARGET.exists():return True
    if cand:cand[0].replace(TARGET);return True
    return False

def reopen():
    import pyautogui
    from pywinauto import Desktop
    focus();pyautogui.hotkey("ctrl","f4");time.sleep(3);pyautogui.press("esc")
    focus();pyautogui.hotkey("ctrl","o");time.sleep(2)
    d=None
    for backend in ("win32","uia"):
        try:
            for q in Desktop(backend=backend).windows():
                try:r=q.rectangle();cls=q.class_name()
                except:continue
                if cls=="#32770" and r.width()>500:d=q;break
            if d:break
        except:pass
    if not d:return False
    try:d.set_focus()
    except:pass
    pyautogui.hotkey("alt","n");time.sleep(.3);pyautogui.hotkey("ctrl","a");pyautogui.write(str(TARGET),interval=.002);pyautogui.press("enter")
    time.sleep(8);shot("50_reopened.png");return True

def main():
    import pyautogui
    pyautogui.FAILSAFE=False
    subprocess.Popen([str(MULTISIM)]);time.sleep(10);dismiss_trial();focus();time.sleep(2)

    # Layout: source at left, total-current ammeter on top rail, inductor and capacitor vertical branches.
    items=[
      ("AC_POWER",350,350,0),
      ("AMMETER",500,220,0),
      ("AMMETER",620,330,1),("INDUCTOR",620,420,1),
      ("AMMETER",800,330,1),("CAPACITOR",800,420,1),
      ("VOLTMETER",930,350,1),
      ("GROUND",350,515,0)
    ]
    for it in items:
        if not place(*it):return 20
    shot("10_components.png")

    set_ac_source(350,350,"220","50")
    set_passive(620,420,"1.432394")
    set_passive(800,420,"8u")
    shot("20_values.png")

    # Detect actual terminals.
    src_t=find_terminal(350,350,"top"); src_b=find_terminal(350,350,"bottom")
    a1_l=find_terminal(500,220,"left"); a1_r=find_terminal(500,220,"right")
    a2_t=find_terminal(620,330,"top"); a2_b=find_terminal(620,330,"bottom")
    L_t=find_terminal(620,420,"top"); L_b=find_terminal(620,420,"bottom")
    a3_t=find_terminal(800,330,"top"); a3_b=find_terminal(800,330,"bottom")
    C_t=find_terminal(800,420,"top"); C_b=find_terminal(800,420,"bottom")
    V_t=find_terminal(930,350,"top"); V_b=find_terminal(930,350,"bottom")
    g_t=find_terminal(350,515,"top")

    # Top source through A1 to top bus.
    wire_path([src_t,(420,220),a1_l])
    wire_path([a1_r,(560,220),(900,220)])
    # Bottom bus back to source.
    wire_path([src_b,(350,500),(900,500)])
    # Coil branch.
    wire_path([(620,220),a2_t]); wire_path([a2_b,L_t]); wire_path([L_b,(620,500)])
    # Capacitor branch.
    wire_path([(800,220),a3_t]); wire_path([a3_b,C_t]); wire_path([C_b,(800,500)])
    # Voltmeter and ground.
    wire_path([(900,220),(930,220),V_t]); wire_path([V_b,(930,500),(900,500)])
    wire_path([g_t,(350,500)])
    shot("30_wired.png")

    if not save_as():return 21
    shot("40_saved.png")
    if not reopen():return 22

    # 9 C states in the SAME native design. Save screenshot for every run.
    for cuf in [0,2,4,6,8,10,12,14,16]:
        set_passive(800,420,(str(cuf)+"u") if cuf else "1p")
        focus();pyautogui.press("f5");time.sleep(4);shot(f"C_{cuf:02d}uF_run.png");pyautogui.press("f5");time.sleep(.5)

    set_passive(800,420,"8u")
    focus();pyautogui.hotkey("ctrl","s");time.sleep(3)
    shot("99_final.png")
    log("LAB3_NATIVE_DONE")
    return 0

if __name__=="__main__":
    try:sys.exit(main())
    except Exception:
        log(traceback.format_exc())
        try:shot("exception.png")
        except:pass
        sys.exit(99)
