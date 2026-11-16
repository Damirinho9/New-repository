import json, subprocess, sys, time
from pathlib import Path
import pyautogui as pg
from pywinauto import Desktop

MULTISIM=Path(sys.argv[1])
ROOT=Path(sys.argv[2]).resolve()
OUT=ROOT/"native-ui"
OUT.mkdir(parents=True,exist_ok=True)
pg.FAILSAFE=False

def windows(backend="win32"):
    try:return Desktop(backend=backend).windows()
    except Exception:return []

def dismiss():
    labels={"Remind Me Later","Continue","Evaluate","Start Trial","OK"}
    for _ in range(5):
        hit=False
        for backend in ("uia","win32"):
            for w in windows(backend):
                try:
                    for e in w.descendants():
                        try:
                            t=e.window_text().replace("&","").strip()
                            if t in labels and e.is_visible():
                                e.click_input(); time.sleep(2); hit=True; break
                        except Exception: pass
                    if hit: break
                except Exception: pass
            if hit: break
        if not hit: break

def main_window(stem):
    cand=[]
    for w in windows("win32"):
        try:
            t=w.window_text(); r=w.rectangle()
            if "Multisim" in t and stem.lower() in t.lower() and r.width()>500 and r.height()>300:
                cand.append((r.width()*r.height(),w,t))
        except Exception:pass
    cand.sort(key=lambda x:-x[0])
    return cand[0][1:] if cand else (None,"")

def waitwin(stem,timeout=40):
    end=time.time()+timeout
    last=""
    while time.time()<end:
        dismiss()
        w,t=main_window(stem); last=t
        if w:return w,t
        time.sleep(1)
    return None,last

def snap(w,path):
    try:
        w.restore(); w.set_focus(); time.sleep(1); pg.press("f7"); time.sleep(3)
    except Exception:pass
    r=w.rectangle()
    pg.screenshot(region=(max(0,r.left),max(0,r.top),max(10,r.width()),max(10,r.height()))).save(str(path))

results={}
for state in ("DARK","THRESHOLD","LIGHT"):
    target=ROOT/f"7330744_PhotoRelay_V6_{state}.ms14"
    if not target.exists(): raise FileNotFoundError(target)
    subprocess.run(["taskkill","/IM","Multisim.exe","/T","/F"],capture_output=True)
    time.sleep(2)
    subprocess.Popen([str(MULTISIM),str(target)])
    w,title=waitwin(target.stem)
    if not w: raise RuntimeError(f"{state}: Multisim window not found: {title}")
    snap(w,OUT/f"{state}_opened.png")
    pg.hotkey("ctrl","s"); time.sleep(4); dismiss()
    saved_title=w.window_text()
    # Actual interactive run. COM transient has already gated numerical correctness.
    try:
        w.set_focus(); pg.press("f5"); time.sleep(6)
    except Exception:pass
    snap(w,OUT/f"{state}_running.png")
    try:
        w.set_focus(); pg.press("f5"); time.sleep(1)
    except Exception:pass
    subprocess.run(["taskkill","/IM","Multisim.exe","/T","/F"],capture_output=True)
    time.sleep(2)
    subprocess.Popen([str(MULTISIM),str(target)])
    w2,title2=waitwin(target.stem)
    if not w2: raise RuntimeError(f"{state}: reopen failed: {title2}")
    snap(w2,OUT/f"{state}_reopened.png")
    results[state]={"opened_title":title,"saved_title":saved_title,"reopened_title":title2,
                    "save_close_reopen":True,"size_bytes":target.stat().st_size}
    subprocess.run(["taskkill","/IM","Multisim.exe","/T","/F"],capture_output=True)
    time.sleep(2)

(OUT/"native_stage3_verification.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(results,ensure_ascii=False,indent=2))
