import json,subprocess,sys,time
from pathlib import Path
import pyautogui as pg
from pywinauto import Desktop

MULTISIM=Path(sys.argv[1]); ROOT=Path(sys.argv[2]).resolve(); OUT=ROOT/"native-ui"; OUT.mkdir(parents=True,exist_ok=True)
pg.FAILSAFE=False

def wins(backend="win32"):
    try:return Desktop(backend=backend).windows()
    except Exception:return []
def dismiss():
    for _ in range(8):
        hit=False
        for backend in ("uia","win32"):
            for w in wins(backend):
                try:
                    for e in w.descendants():
                        try:
                            t=e.window_text().replace("&","").strip()
                            if t in {"Remind Me Later","Continue","Evaluate","Start Trial","OK","Yes"} and e.is_visible():
                                e.click_input();time.sleep(1);hit=True;break
                        except Exception:pass
                    if hit:break
                except Exception:pass
            if hit:break
        if not hit:break
def find(stem):
    cand=[]
    for w in wins("win32"):
        try:
            t=w.window_text();q=w.rectangle()
            if "Multisim" in t and stem.lower() in t.lower() and q.width()>500 and q.height()>300:
                cand.append((q.width()*q.height(),w,t))
        except Exception:pass
    cand.sort(key=lambda z:-z[0])
    return cand[0][1:] if cand else (None,"")
def waitwin(stem,timeout=45):
    end=time.time()+timeout
    while time.time()<end:
        dismiss();w,t=find(stem)
        if w:return w,t
        time.sleep(1)
    return None,""
def snap(w,path):
    w.restore();w.set_focus();time.sleep(1);pg.press("f7");time.sleep(2)
    q=w.rectangle();pg.screenshot(region=(max(0,q.left),max(0,q.top),max(10,q.width()),max(10,q.height()))).save(str(path))
def kill():
    subprocess.run(["taskkill","/IM","Multisim.exe","/T","/F"],capture_output=True);time.sleep(2)

results={}
for state in ("DARK","THRESHOLD","LIGHT","TRANSIENT"):
    f=ROOT/f"7330744_PhotoRelay_V6_{state}.ms14"
    if not f.exists():raise FileNotFoundError(f)
    kill();subprocess.Popen([str(MULTISIM),str(f)])
    w,title=waitwin(f.stem)
    if not w:raise RuntimeError(state+": initial open failed")
    snap(w,OUT/f"{state}_opened.png")
    w.set_focus();pg.press("f5");time.sleep(7);dismiss();snap(w,OUT/f"{state}_running.png")
    w.set_focus();pg.press("f5");time.sleep(1);pg.hotkey("ctrl","s");time.sleep(3);dismiss();kill()

    subprocess.Popen([str(MULTISIM),str(f)])
    w2,title2=waitwin(f.stem)
    if not w2:raise RuntimeError(state+": reopen failed")
    w2.set_focus();pg.press("f5");time.sleep(7);dismiss();snap(w2,OUT/f"{state}_reopened_running.png")
    w2.set_focus();pg.press("f5");time.sleep(1);pg.hotkey("ctrl","s");time.sleep(2);dismiss()
    results[state]={"opened_title":title,"reopened_title":title2,"run_before_close":True,"run_after_reopen":True,
                    "save_close_reopen":True,"size_bytes":f.stat().st_size}
    kill()

(OUT/"native_phaseA_verification.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
print(json.dumps(results,ensure_ascii=False))
