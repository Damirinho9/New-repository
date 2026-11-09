import sys,time,subprocess,json,traceback
from pathlib import Path
import pyautogui as pg
from pywinauto import Desktop
import native_helpers as h

def dump(d,name):
    rows=[]
    for e in d.descendants():
        try:
            r=e.rectangle()
            if r.width()>0 and r.height()>0:rows.append({'text':e.window_text(),'class':e.class_name(),'rect':list(r),'id':e.control_id()})
        except Exception:pass
    (h.OUT/(name+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    h.shot(name+'.png')

try:
    pg.FAILSAFE=False
    subprocess.Popen([str(h.MULTISIM)]);time.sleep(12)
    if h.trial_present():h.dismiss_trial()
    # Dismiss the ordinary reminder only, never activation or terms.
    for w in Desktop(backend='win32').windows():
        for e in w.descendants():
            try:
                if e.window_text().strip() in ['Remind Me Later','Continue'] and e.is_visible():e.click_input();time.sleep(4)
            except Exception:pass
    w=h.focus()
    if not w:raise RuntimeError('Multisim main window missing')
    h.shot('00_workspace.png')
    for query in ['DC_CURRENT','VOLTAGE_CONTROLLED','ABM','SWITCH','AC_POWER','VOLTMETER']:
        d=h.comp_dialog()
        if not d:raise RuntimeError('Select a Component dialog missing')
        r=d.rectangle();pg.click(r.left+300,r.top+65);pg.hotkey('ctrl','a');pg.write(query,interval=.04);time.sleep(2)
        dump(d,'search_'+query)
        pg.press('esc');time.sleep(.4)
    h.log('COMPONENT_PROBE_COMPLETE')
except Exception:
    h.log(traceback.format_exc());h.shot('99_exception.png');sys.exit(1)
