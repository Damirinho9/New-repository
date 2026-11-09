"""Bounded native UI correction actions for an already running Multisim session."""
import sys,time,json,subprocess,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'native7330744'))
import pyautogui as pg
import win32gui
from pywinauto import Desktop
import native_helpers as h

pg.FAILSAFE=False
commands=json.loads(Path(sys.argv[3]).read_text(encoding='utf-8-sig'))
target=h.OUT/'7330744_PhotoRelay_V6.ms14'

def dialog():
    return Desktop(backend='win32').window(handle=win32gui.GetForegroundWindow())

def controls(tag):
    d=dialog();rows=[]
    for e in d.descendants():
        try:
            r=e.rectangle()
            if e.is_visible():rows.append({'text':e.window_text(),'class':e.class_name(),'rect':[r.left,r.top,r.right,r.bottom]})
        except Exception:pass
    (h.OUT/(tag+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    h.shot(tag+'.png')

def capture(name,window=False):
    if window:
        w=h.focus();r=w.rectangle()
        pg.screenshot(region=(max(0,r.left),max(0,r.top),r.width(),r.height())).save(str(h.OUT/name))
    else:h.shot(name)

def save():
    h.focus();pg.hotkey('ctrl','s');time.sleep(2)
    d=dialog()
    if 'save' in d.window_text().lower():
        pg.hotkey('alt','n');pg.hotkey('ctrl','a');pg.write(str(target),interval=.002);pg.press('enter');time.sleep(5)
    if not target.exists() or target.stat().st_size<1000:raise RuntimeError('Native saved file absent')

try:
    for i,a in enumerate(commands['actions']):
        op=a['op'];h.log(f'Action {i} {a}')
        if op=='click':pg.click(a['x'],a['y'],clicks=a.get('clicks',1),interval=.15)
        elif op=='hotkey':pg.hotkey(*a['keys'])
        elif op=='type':pg.write(a['text'],interval=.01)
        elif op=='place':h.place(a['name'],a['x'],a['y'],a.get('rotate',0))
        elif op=='wire':
            h.focus();pg.hotkey('ctrl','q');time.sleep(.2)
            for p in a['points']:pg.click(*p);time.sleep(.2)
            pg.press('esc')
        elif op=='value':h.set_value(a['x'],a['y'],a['value'],a.get('unit'))
        elif op=='dump':controls(a.get('name',f'controls_{i}'))
        elif op=='edit':
            d=dialog();es=[e for e in d.descendants() if 'Edit' in e.class_name() and e.is_visible()]
            es.sort(key=lambda e:(e.rectangle().top,e.rectangle().left));es[a.get('index',0)].set_edit_text(a['text'])
        elif op=='named_button':
            d=dialog();found=False
            for e in d.descendants():
                if e.window_text().replace('&','').strip()==a['name'] and e.is_visible():e.click_input();found=True;break
            if not found:raise RuntimeError('Button missing '+a['name'])
        elif op=='save':save()
        elif op=='close_reopen':
            save();subprocess.run(['taskkill','/IM','Multisim.exe','/T','/F'],check=False);time.sleep(2)
            subprocess.Popen([str(h.MULTISIM),str(target)]);time.sleep(14)
            for w in Desktop(backend='uia').windows():
                for e in w.descendants():
                    try:
                        if e.window_text().strip()=='Remind Me Later' and e.is_visible():e.click_input();time.sleep(4)
                    except Exception:pass
            w=h.focus()
            if target.stem not in w.window_text():raise RuntimeError('Reopened title does not match native target')
        elif op=='run':h.focus();pg.press('f5');time.sleep(a.get('seconds',8));capture(a.get('name','native_run.png'),a.get('window',True))
        elif op=='stop':h.focus();pg.press('f5');time.sleep(1)
        elif op=='screenshot':capture(a['name'],a.get('window',False))
        else:raise RuntimeError('Unknown native action '+op)
        time.sleep(.4)
    h.shot('actions_'+str(commands['sequence'])+'_complete.png')
except Exception:
    h.log(traceback.format_exc());h.shot('actions_'+str(commands['sequence'])+'_exception.png');sys.exit(1)
