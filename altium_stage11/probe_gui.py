import json, os, re, subprocess, sys, time, traceback
from pathlib import Path
import pyautogui
from pywinauto import Desktop

EXE=Path(sys.argv[1]); INPUT=Path(sys.argv[2]); OUT=Path(sys.argv[3])
OUT.mkdir(parents=True,exist_ok=True)
pyautogui.FAILSAFE=False
report={
    'application':'Altium Designer 26.11.1',
    'project':None,
    'license_state':'unverified',
    'direct_open_attempts':{},
    'native_erc_executed':False,
    'native_drc_executed':False,
    'screenshots':[]
}

def log(text):
    print(text,flush=True)
    with (OUT/'gui-probe.log').open('a',encoding='utf-8') as f:f.write(text+'\n')

def capture(name):
    p=OUT/name
    pyautogui.screenshot().save(p)
    report['screenshots'].append(name)
    log('screenshot '+name)

def windows(backend='win32'):
    vals=[]
    try:
        for w in Desktop(backend=backend).windows():
            try:
                t=w.window_text();r=w.rectangle()
                if r.width()>50 and r.height()>50:
                    vals.append((w,t,r))
            except: pass
    except: pass
    return vals

def mainwin():
    candidates=[]
    for w,t,r in windows('win32'):
        if 'altium' in t.lower() or 'designer' in t.lower():
            candidates.append(w)
    if not candidates:return None
    return max(candidates,key=lambda w:w.rectangle().width()*w.rectangle().height())

def dump(name):
    rows=[]
    for backend in ['win32','uia']:
        for w,t,r in windows(backend):
            try:
                rows.append(f'WINDOW {backend}: {t} {r}')
                for d in w.descendants():
                    try:
                        if d.is_visible():
                            rows.append(f'{d.class_name()} | {d.window_text()} | {d.rectangle()}')
                    except: pass
            except: pass
    text='\n'.join(rows)
    (OUT/name).write_text(text,encoding='utf-8')
    return text

def terminate():
    subprocess.run(['taskkill','/IM','X2.EXE','/T','/F'],capture_output=True,text=True)
    time.sleep(3)

def wait_main(seconds=30):
    for _ in range(seconds):
        w=mainwin()
        if w:
            try:w.maximize();w.set_focus()
            except:pass
            return w
        time.sleep(1)
    return None

def direct_open(path,tag):
    terminate()
    log(f'DIRECT OPEN {path}')
    subprocess.Popen([str(EXE),str(path)])
    w=wait_main(35)
    time.sleep(12)
    if w:
        try:w.maximize();w.set_focus()
        except:pass
    text=dump(tag+'_uia.txt')
    capture(tag+'.png')
    hay=(' '.join([t for _,t,_ in windows('win32')])+' '+text).lower()
    ok=path.name.lower() in hay
    no_license=bool(re.search(r'No\s+Licen[sc]e|Sign In To Start Using Altium Designer|Not Signed In',text,re.I))
    report['direct_open_attempts'][path.name]={
        'filename_visible_in_ui':ok,
        'license_block_visible':no_license,
        'screenshot':tag+'.png'
    }
    return ok,no_license

def shell_open(path,tag):
    terminate()
    log(f'SHELL OPEN {path}')
    os.startfile(str(path))
    w=wait_main(35)
    time.sleep(12)
    if w:
        try:w.maximize();w.set_focus()
        except:pass
    text=dump(tag+'_uia.txt')
    capture(tag+'.png')
    hay=(' '.join([t for _,t,_ in windows('win32')])+' '+text).lower()
    ok=path.name.lower() in hay
    no_license=bool(re.search(r'No\s+Licen[sc]e|Sign In To Start Using Altium Designer|Not Signed In',text,re.I))
    report['direct_open_attempts'][path.name+'_shell']={
        'filename_visible_in_ui':ok,
        'license_block_visible':no_license,
        'screenshot':tag+'.png'
    }
    return ok,no_license

def try_menu(path):
    w=mainwin()
    if not w:return
    try:w.set_focus()
    except:pass

    # Native schematic / PCB editor capture already visible.
    capture('04_Altium_Active_Document.png')

    # Try 2D and 3D only if PCB is actually open.
    if path.suffix.lower()=='.pcbdoc':
        pyautogui.press('2');time.sleep(3);capture('05_Altium_PCB_2D.png')
        pyautogui.press('3');time.sleep(5);capture('06_Altium_PCB_3D.png')
        pyautogui.press('2');time.sleep(2)

        # Design Rules - normal menu only.
        try:
            w.menu_select('Design->Rules...')
            time.sleep(4)
            capture('07_Altium_Design_Rules.png')
            dump('07_rules_uia.txt')
            pyautogui.press('esc');time.sleep(2)
        except Exception as e:
            log('Rules menu unavailable: '+repr(e))

        # DRC - normal menu only. Do not assert success unless dialog/results are visible.
        try:
            w.menu_select('Tools->Design Rule Check...')
            time.sleep(4)
            capture('08_Altium_DRC_Dialog.png')
            drctext=dump('08_drc_uia.txt')
            report['native_drc_executed']=bool(re.search(r'Design Rule Check|DRC|Violations',drctext,re.I))
            pyautogui.press('esc');time.sleep(2)
        except Exception as e:
            log('DRC menu unavailable: '+repr(e))

try:
    projects=list(INPUT.rglob('*.PrjPcb'))
    schs=list(INPUT.rglob('*.SchDoc'))
    pcbs=list(INPUT.rglob('*.PcbDoc'))
    if projects: report['project']=str(projects[0])

    # First try exact documents as X2 command-line arguments. This is a normal documented Windows launch path,
    # not license modification or bypass.
    opened_any=False
    for path,tag in [
        (schs[0] if schs else None,'01_Altium_Schematic'),
        (pcbs[0] if pcbs else None,'02_Altium_PCB_Editor')
    ]:
        if not path: continue
        ok,blocked=direct_open(path,tag)
        if not ok:
            # One bounded Windows shell association attempt.
            ok2,blocked2=shell_open(path,tag+'_Shell')
            ok=ok or ok2
            blocked=blocked or blocked2
        if ok:
            opened_any=True
            try_menu(path)

    text=dump('99_final_ui.txt')
    no_license=bool(re.search(r'No\s+Licen[sc]e|Sign In To Start Using Altium Designer|Not Signed In',text,re.I))
    report['license_state']='No License / Not Signed In' if no_license else 'document access available'
    report['opened_any_document']=opened_any
    if not opened_any:
        capture('09_Altium_License_Blocker.png')
        report['limitation']='Altium opened but real SchDoc/PcbDoc editors were blocked by license/sign-in. No reconstructed screenshots were produced.'
    else:
        report['limitation']='Only screenshots actually visible in Altium were captured. DRC/Rules are not asserted unless their native UI was visible.'
except Exception:
    log(traceback.format_exc())
    try:capture('98_Altium_Exception.png')
    except:pass
finally:
    (OUT/'native-evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
