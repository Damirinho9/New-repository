import json, os, re, subprocess, sys, time, traceback
from pathlib import Path
import pyautogui
from pywinauto import Desktop

EXE=Path(sys.argv[1]); INPUT=Path(sys.argv[2]); OUT=Path(sys.argv[3])
OUT.mkdir(parents=True,exist_ok=True)
pyautogui.FAILSAFE=False
report={'application':'Altium Designer 26.11.1','project':None,'license_state':'unverified','native_erc_executed':False,'native_drc_executed':False,'native_rules_saved':False,'screenshots':[],'documents':{}}

def log(text):
    print(text,flush=True)
    with (OUT/'gui-probe.log').open('a',encoding='utf-8') as f:f.write(text+'\n')

def capture(name):
    p=OUT/name;pyautogui.screenshot().save(p);report['screenshots'].append(name);log('screenshot '+name)

def windows():
    vals=[]
    for w in Desktop(backend='win32').windows():
        try:
            t=w.window_text();r=w.rectangle()
            if r.width()>50 and r.height()>50:vals.append((w,t,r))
        except:pass
    return vals

def main():
    candidates=[w for w,t,r in windows() if 'altium' in t.lower()]
    if not candidates:return None
    return max(candidates,key=lambda w:w.rectangle().width()*w.rectangle().height())

def dump(name):
    rows=[]
    for backend in ['win32','uia']:
        try:
            for w in Desktop(backend=backend).windows():
                try:
                    if 'altium' not in w.window_text().lower() and w.process_id() not in [x[0].process_id() for x in windows() if 'altium' in x[1].lower()]:continue
                    rows.append(f'WINDOW {backend}: {w.window_text()} {w.rectangle()}')
                    for d in w.descendants():
                        try:
                            if d.is_visible():rows.append(f'{d.class_name()} | {d.window_text()} | {d.rectangle()}')
                        except:pass
                except:pass
        except Exception as e:rows.append(str(e))
    text='\n'.join(rows);(OUT/name).write_text(text,encoding='utf-8');return text

def open_document(path,tag):
    w=main()
    if not w:return False
    try:w.set_focus()
    except:pass
    pyautogui.hotkey('ctrl','o');time.sleep(2)
    dialogs=[]
    for d,t,r in windows():
        if re.fullmatch(r'Open.*|Choose.*|Select.*',t,re.I):dialogs.append(d)
    if not dialogs:
        capture(tag+'_open_unavailable.png');log('open dialog unavailable '+str(path));return False
    d=dialogs[0]
    try:d.set_focus()
    except:pass
    pyautogui.hotkey('alt','n');pyautogui.hotkey('ctrl','a');pyautogui.write(str(path),interval=.002);pyautogui.press('enter');time.sleep(8)
    text=dump(tag+'_uia.txt');capture(tag+'.png')
    names=[t for w,t,r in windows()]
    ok=path.name.lower() in (' '.join(names)+' '+text).lower()
    report['documents'][path.name]={'filename_visible_in_ui':ok,'evidence':tag+'.png'}
    return ok

try:
    subprocess.Popen([str(EXE)])
    for i in range(30):
        time.sleep(2)
        if main():break
    w=main()
    if w:
        try:w.maximize();w.set_focus()
        except:pass
    time.sleep(10);capture('00_Altium_License.png')
    text=dump('00_license_uia.txt')
    no_license=bool(re.search(r'No\s+Licen[sc]e|not\s+licen[sc]ed|licen[sc]e\s+is\s+required|without\s+a\s+licen[sc]e',text,re.I))
    report['license_state']='No License' if no_license else 'unverified'
    report['trial_account_available']=False
    # View and normal menu attempts only. No license bypass, account creation, or script injection.
    projects=list(INPUT.rglob('*.PrjPcb'))
    if projects:
        report['project']=str(projects[0]);open_document(projects[0],'01_Project')
    for ext,tag in [('*.SchDoc','02_Altium_Schematic'),('*.PcbDoc','03_PCB_Placement')]:
        files=list(INPUT.rglob(ext))
        if files:open_document(files[0],tag)
    if report['documents'].get('PhotoRelay_V6.PcbDoc',{}).get('filename_visible_in_ui'):
        w=main()
        try:w.set_focus()
        except:pass
        pyautogui.press('3');time.sleep(3);capture('04_PCB_3D.png')
        pyautogui.press('2');time.sleep(2)
        # Observe the normal Rules command. Do not save any modifications without licensed editing.
        try:
            w.menu_select('Design->Rules...');time.sleep(2);capture('05_Altium_Rules.png');dump('05_rules_uia.txt');pyautogui.press('esc')
        except Exception as e:log('Rules command unavailable: '+str(e))
    report['limitation']='No authenticated Altium Account/license was supplied. Editing, rule saving, compile, ERC and DRC are not asserted. Viewer/trial acquisition requires an Altium Account.'
except Exception:
    log(traceback.format_exc())
    try:capture('99_exception.png')
    except:pass
finally:
    (OUT/'native-evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
