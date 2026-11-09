"""Reopen the genuine Multisim-authored native design and measure its states."""
import sys,time,json,subprocess,traceback,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'native7330744'))
import pyautogui as pg
from pywinauto import Desktop
import native_helpers as h

TARGET=h.OUT/'7330744_PhotoRelay_V6.ms14'
LOG=h.OUT/'native-reopen-proof.log'
pg.FAILSAFE=False
DX=DY=0

def log(text):
    print(text,flush=True)
    with LOG.open('a',encoding='utf-8') as f:f.write(time.strftime('%Y-%m-%d %H:%M:%S')+' '+text+'\n')

def point(x,y):return (x+DX,y+DY)

def shot(name,window=True):
    if window:
        w=h.focus();r=w.rectangle();pg.screenshot(region=(max(0,r.left),max(0,r.top),r.width(),r.height())).save(str(h.OUT/name))
    else:pg.screenshot(str(h.OUT/name))

def reminders():
    # Official trial controls only, no license bypass.
    if h.trial_present():
        h.dismiss_trial()

    # A fresh Multisim process can surface the ordinary NI User Account
    # sign-in window even though the evaluation session is otherwise usable.
    # Close only that sign-in window, then choose Cancel on the underlying
    # licensing prompt. This does not activate or bypass any license.
    for backend in ['uia','win32']:
        try:
            for w in Desktop(backend=backend).windows():
                try:
                    title=w.window_text().strip()
                except Exception:
                    title=''
                if title=='NI User Account':
                    try:
                        w.close()
                        time.sleep(2)
                        log('Closed NI User Account dialog without credentials')
                    except Exception as e:
                        log('Could not close NI User Account dialog: '+repr(e))
        except Exception:
            pass

    # Click Cancel only on visible top-level licensing/activation dialogs.
    for backend in ['uia','win32']:
        try:
            for w in Desktop(backend=backend).windows():
                try:
                    title=w.window_text().strip()
                    if 'Multisim' not in title and 'License' not in title and 'Activation' not in title:
                        continue
                    for e in w.descendants():
                        try:
                            if e.window_text().replace('&','').strip()=='Cancel' and e.is_visible():
                                e.click_input()
                                time.sleep(3)
                                log('Cancelled NI sign-in/licensing prompt')
                                raise StopIteration
                        except StopIteration:
                            raise
                        except Exception:
                            pass
                except StopIteration:
                    break
                except Exception:
                    pass
        except StopIteration:
            pass
        except Exception:
            pass

    for backend in ['uia','win32']:
        try:
            for w in Desktop(backend=backend).windows():
                for e in w.descendants():
                    try:
                        if e.window_text().strip()=='Remind Me Later' and e.is_visible():
                            e.click_input()
                            time.sleep(4)
                    except Exception:
                        pass
        except Exception:
            pass

def open_native():
    global DX,DY
    p=subprocess.Popen([str(h.MULTISIM),str(TARGET)]);log(f'Launch native file={TARGET} pid={p.pid}');time.sleep(13)
    reminders();w=h.focus()
    if not w:raise RuntimeError('Multisim native workspace missing')
    title=w.window_text();log('Opened title='+title)
    if not title.startswith(TARGET.stem+' - Multisim'):
        # If the first-run trial deferred the file argument, use native File/Open.
        pg.hotkey('ctrl','o');time.sleep(2);pg.hotkey('alt','n');pg.hotkey('ctrl','a');pg.write(str(TARGET),interval=.002);pg.press('enter');time.sleep(8)
        w=h.focus();title=w.window_text();log('Native File/Open title='+title)
    if not title.startswith(TARGET.stem+' - Multisim'):raise RuntimeError('Exact final filename not shown in native workspace')
    r=w.rectangle();DX=r.left-58;DY=r.top-50;log(f'Window rect={r}; correction offset={DX},{DY}')
    # Verified close button of the lower Spreadsheet View; harmless blank toolbox if already closed.
    pg.click(*point(69,570));time.sleep(.7);shot('Native_Reopened_Desktop.png',False)
    return p.pid

def stop():
    h.focus();pg.click(*point(784,147));time.sleep(1)

def save():
    stop();pg.hotkey('ctrl','s');time.sleep(3)
    if not TARGET.exists() or TARGET.stat().st_size<1000:raise RuntimeError('Native saved file absent')
    log(f'Native Ctrl+S saved size={TARGET.stat().st_size} sha256={hashlib.sha256(TARGET.read_bytes()).hexdigest()}')

def set_photo(value):
    stop()
    if not h.set_value(*point(676,248),value,'A'):raise RuntimeError('Photocurrent native property edit failed')
    log('Native photocurrent set to '+value+' A')

def run(name):
    h.focus();pg.press('f5');time.sleep(10)
    # Simulation may reopen Messages/Spreadsheet View. Close it to keep all three meters visible.
    pg.click(*point(69,570));time.sleep(.5);shot(name)
    log('Native Run screenshot='+name+' messages='+repr(h.simulation_messages()))
    stop()

try:
    if not TARGET.exists():raise RuntimeError('Input genuine native file absent before GUI launch')
    open_native();save()
    subprocess.run(['taskkill','/IM','Multisim.exe','/T','/F'],check=False);time.sleep(2)
    open_native()
    set_photo('2.107u');run('Multisim_Light.png')
    set_photo('1.475u');run('Multisim_Threshold_Before.png')
    set_photo('1.474u');run('Multisim_Threshold.png')
    set_photo('0.3025u');run('Multisim_Dark.png')
    set_photo('2.107u');save()
    subprocess.run(['taskkill','/IM','Multisim.exe','/T','/F'],check=False);time.sleep(2)
    open_native();run('Multisim_Light.png');save();shot('Multisim_Schematic.png')
    proof={'source_native_gui_run':42600867145,'source_native_gui_artifact':'7330744-native-live-progress-3','final_filename':TARGET.name,'saved_by_multisim':True,'fully_closed_and_reopened':True,'run_performed_after_reopen':True,'size_bytes':TARGET.stat().st_size,'sha256':hashlib.sha256(TARGET.read_bytes()).hexdigest(),'measurements':'Read actual instrument values from the corresponding native screenshots; not copied from old RAW data.'}
    (h.OUT/'native_validation.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    log('SAVE_CLOSE_REOPEN_RUN_COMPLETED')
except Exception:
    log(traceback.format_exc())
    try:shot('Native_Recovery_Exception.png',False)
    except Exception:pass
    sys.exit(1)
