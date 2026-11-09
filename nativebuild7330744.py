"""Native Multisim GUI functional PhotoRelay model; no file serialization/import."""
import sys,time,subprocess,json,traceback,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'native7330744'))
import pyautogui as pg
import win32gui
from pywinauto import Desktop
import native_helpers as h

h.TARGET=h.OUT/'7330744_PhotoRelay_V6.ms14'
h.LOG=h.OUT/'7330744-native.log'

def dump(d,name):
    rows=[]
    for e in d.descendants():
        try:
            r=e.rectangle()
            if r.width()>0 and r.height()>0:rows.append({'text':e.window_text(),'class':e.class_name(),'rect':[r.left,r.top,r.right,r.bottom],'id':e.control_id()})
        except Exception:pass
    (h.OUT/(name+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    h.shot(name+'.png')

def dismiss_reminders():
    for _ in range(3):
        clicked=False
        for backend in ['uia','win32']:
            for w in Desktop(backend=backend).windows():
                for e in w.descendants():
                    try:
                        name=e.window_text().replace('&','').strip()
                        if name in ['Remind Me Later','Continue','Evaluate','Start Trial'] and e.is_visible():
                            e.click_input();time.sleep(4);clicked=True;break
                    except Exception:pass
                if clicked:break
            if clicked:break
        if not clicked:break

def launch():
    subprocess.Popen([str(h.MULTISIM)]);time.sleep(12)
    if h.trial_present():h.dismiss_trial()
    dismiss_reminders()
    w=h.focus()
    if not w or 'Design' not in w.window_text():
        h.shot('blocked_main_window.png');raise RuntimeError('Native Multisim Design window absent')
    # Close Spreadsheet View using its actual close button verified in run 42597839152.
    pg.click(69,570);time.sleep(.7);h.shot('00_canvas_expanded.png')
    return w

def blue_clusters(box):
    im=pg.screenshot().convert('RGB');x0,y0,x1,y1=box;points=set()
    for y in range(max(0,y0),min(im.height,y1)):
        for x in range(max(0,x0),min(im.width,x1)):
            r,g,b=im.getpixel((x,y))
            if (b>145 and r<105 and g<190) or (r>160 and g<130 and b<130):points.add((x,y))
    clusters=[]
    while points:
        seed=points.pop();stack=[seed];part=[seed]
        while stack:
            x,y=stack.pop()
            for p in [(x-1,y),(x+1,y),(x,y-1),(x,y+1)]:
                if p in points:points.remove(p);stack.append(p);part.append(p)
        xs=[p[0] for p in part];ys=[p[1] for p in part]
        width=max(xs)-min(xs)+1;height=max(ys)-min(ys)+1
        if 2<=len(part)<=100 and width<=14 and height<=14:
            clusters.append((round(sum(xs)/len(xs)),round(sum(ys)/len(ys)),len(part)))
    return clusters

def pins(x,y,width=45):
    # Real Multisim terminals in run 42599163152 are black, not blue/red.
    im=pg.screenshot().convert('RGB');rows=[]
    for yy in range(y-8,y+9):
        xs=[xx for xx in range(x-10,x+width+15) if max(im.getpixel((xx,yy)))<120]
        if xs:rows.append((len(xs),yy,min(xs),max(xs)))
    rows.sort(reverse=True)
    h.log(f'black terminal rows at {x},{y} width={width}: {rows[:4]}')
    if not rows or rows[0][3]-rows[0][2]<width*.7:raise RuntimeError(f'Cannot verify native terminals near {x},{y}')
    count,yy,x1,x2=rows[0];return [(x1,yy),(x2,yy)]

def path(points):
    h.focus();pg.moveTo(*points[0],duration=.08);pg.click();time.sleep(.25)
    for p in points[1:]:pg.moveTo(*p,duration=.1);pg.click();time.sleep(.2)
    pg.press('esc');time.sleep(.35)

def name_wire(point,name):
    h.focus();pg.doubleClick(*point,interval=.15);time.sleep(1)
    dlg=Desktop(backend='win32').window(handle=win32gui.GetForegroundWindow())
    dump(dlg,'net_'+name)
    if dlg.class_name()!='#32770':pg.press('esc');raise RuntimeError('Wire properties dialog absent '+name)
    edits=[e for e in dlg.descendants() if 'Edit' in e.class_name() and e.is_visible()]
    if not edits:pg.press('esc');raise RuntimeError('Net name edit absent '+name)
    edits.sort(key=lambda e:e.rectangle().top)
    edits[0].set_edit_text(name)
    for e in dlg.descendants():
        try:
            if e.window_text().replace('&','').strip()=='OK':e.click_input();time.sleep(1);return
        except Exception:pass
    pg.press('enter');time.sleep(1)

def property_value(point,value,tag):
    h.focus();pg.doubleClick(*point,interval=.15);time.sleep(1)
    dlg=Desktop(backend='win32').window(handle=win32gui.GetForegroundWindow())
    dump(dlg,'property_'+tag)
    if dlg.class_name()!='#32770':pg.press('esc');raise RuntimeError('Property dialog absent '+tag)
    visible=[e for e in dlg.descendants() if 'Edit' in e.class_name() and e.is_visible()]
    visible.sort(key=lambda e:(e.rectangle().top,e.rectangle().left))
    if not visible:pg.press('esc');raise RuntimeError('Property value edit absent '+tag)
    visible[0].set_edit_text(value)
    for e in dlg.descendants():
        try:
            if e.window_text().replace('&','').strip()=='OK':e.click_input();time.sleep(1);return
        except Exception:pass
    pg.press('enter');time.sleep(1)

def center(pair):return tuple(round((pair[0][i]+pair[1][i])/2) for i in [0,1])

def save_partial():
    pg.press('esc',presses=2,interval=.1);h.focus();pg.hotkey('ctrl','s');time.sleep(2)
    d=Desktop(backend='win32').window(handle=win32gui.GetForegroundWindow())
    if 'save' in d.window_text().lower():
        partial=h.OUT/'7330744_PhotoRelay_V6_Partial.ms14'
        pg.hotkey('alt','n');pg.hotkey('ctrl','a');pg.write(str(partial),interval=.002);pg.press('enter');time.sleep(5)
    h.shot('partial_saved.png')

def save_final_as():
    h.focus();pg.hotkey('alt','f');time.sleep(.7);found=False
    menu_names=[]
    for w in Desktop(backend='uia').windows():
        for e in w.descendants():
            try:
                name=e.window_text().replace('&','').strip();menu_names.append(name)
                if name.lower().startswith('save as') and e.is_visible():e.click_input();found=True;break
            except Exception:pass
        if found:break
    (h.OUT/'file_menu_items.json').write_text(json.dumps(menu_names,ensure_ascii=False,indent=2))
    if not found:
        h.shot('file_menu_save_as_needed.png');raise RuntimeError('Save As menu needs verified coordinate correction')
    time.sleep(1)
    d=Desktop(backend='win32').window(handle=win32gui.GetForegroundWindow())
    dump(d,'final_save_as_dialog')
    if 'save' not in d.window_text().lower():raise RuntimeError('Save As dialog not visible')
    pg.hotkey('alt','n');pg.hotkey('ctrl','a');pg.write(str(h.TARGET),interval=.002);pg.press('enter');time.sleep(5)
    if not h.TARGET.exists() or h.TARGET.stat().st_size<1000:raise RuntimeError('Final native Save As did not produce file')

def set_meter_ac(point):
    h.focus();pg.doubleClick(*point,interval=.15);time.sleep(1)
    dlg=Desktop(backend='win32').window(handle=win32gui.GetForegroundWindow())
    dump(dlg,'load_meter_mode')
    if dlg.class_name()!='#32770':raise RuntimeError('Load meter property dialog absent')
    for e in dlg.descendants():
        try:
            if e.window_text().strip().upper()=='AC' and e.is_visible():
                e.click_input();time.sleep(.3)
                for b in dlg.descendants():
                    if b.window_text().replace('&','').strip()=='OK':b.click_input();time.sleep(1);return
        except Exception:pass
    pg.press('esc');raise RuntimeError('AC RMS meter mode control absent')

def run_capture(name):
    w=h.focus();pg.press('f5');time.sleep(9)
    r=w.rectangle();pg.screenshot(region=(max(0,r.left),max(0,r.top),r.width(),r.height())).save(str(h.OUT/name))
    (h.OUT/(name+'.messages.json')).write_text(json.dumps(h.simulation_messages(),indent=2),encoding='utf-8')
    pg.press('f5');time.sleep(1)

def main():
    pg.FAILSAFE=False;launch()
    # All objects are placed from the installed Multisim database, on one sheet.
    items=[
        ('V12','DC_POWER',330,245,1,36),('R1','RESISTOR',430,245,0,45),('R2','RESISTOR',520,245,0,45),
        ('PHOTO','DC_CURRENT',650,245,1,54),('SENS_METER','VOLTMETER',780,245,0,99),
        ('CTRL','ABM_VOLTAGE',330,390,1,54),('CTRL_R','RESISTOR',500,390,0,45),('CTRL_METER','VOLTMETER',680,390,0,99),
        ('AC','AC_POWER',330,530,1,54),('KEY','ABM_CURRENT',470,530,1,54),('LOAD','RESISTOR',650,530,0,45),
        ('LOAD_METER','VOLTMETER',800,530,0,99),
    ]
    for ref,component,x,y,rot,width in items:
        if not h.place(component,x,y,rot):raise RuntimeError('Placement failed '+ref)
    h.place('GROUND',350,330,0)
    h.shot('10_native_components.png')
    final_target=h.TARGET;h.TARGET=h.OUT/'7330744_PhotoRelay_V6_Partial.ms14'
    if not h.save_as():raise RuntimeError('Partial native component placement could not be saved')
    h.TARGET=final_target
    p={ref:pins(x,y,width) for ref,component,x,y,rot,width in items}
    (h.OUT/'terminal_coordinates.json').write_text(json.dumps(p,indent=2))
    # DC sensor chain and permanent SENS measurement.
    sensor_y=p['R1'][0][1]
    path([p['V12'][1],p['R1'][0]]);path([p['R1'][1],p['R2'][0]])
    path([p['R2'][1],p['PHOTO'][0]])
    sx=round((p['R2'][1][0]+p['PHOTO'][0][0])/2);sy=sensor_y
    name_wire((sx,sy),'SENS')
    path([p['PHOTO'][1],(740,sensor_y),(740,300),(310,300),(310,sensor_y),p['V12'][0]])
    path([p['SENS_METER'][0],(770,sensor_y),(770,275),(635,275),(635,sensor_y)])
    path([p['SENS_METER'][1],(920,sensor_y),(920,300),(740,300)])
    # Ground terminal is observed by color / cursor refinement at its native location.
    im=pg.screenshot().convert('RGB')
    candidates=[(xx,yy) for yy in range(320,350) for xx in range(340,363) if max(im.getpixel((xx,yy)))<120]
    if not candidates:raise RuntimeError('Ground terminal not verified')
    ground=min(candidates,key=lambda q:(q[1],abs(q[0]-352)))
    path([ground,(350,300)])
    # Behavioral comparator as functional equivalent of the VT1-VT3 controller.
    cy=p['CTRL'][0][1]
    path([p['CTRL'][1],p['CTRL_R'][0]])
    name_wire((round((p['CTRL'][1][0]+p['CTRL_R'][0][0])/2),cy),'GDRV')
    path([p['CTRL_R'][1],(600,cy),(600,445),(310,445),(310,300)])
    path([p['CTRL'][0],(310,cy)])
    path([p['CTRL_METER'][0],(665,cy),(665,420),(450,420),(450,cy)])
    path([p['CTRL_METER'][1],(920,cy),(920,445),(600,445)])
    # Bidirectional behavioral conductance switch, with actual AC source and load.
    ly=p['AC'][0][1]
    path([p['AC'][1],p['KEY'][0]])
    name_wire((round((p['AC'][1][0]+p['KEY'][0][0])/2),ly),'MAINS')
    path([p['KEY'][1],p['LOAD'][0]])
    name_wire((round((p['KEY'][1][0]+p['LOAD'][0][0])/2),ly),'SW')
    path([p['AC'][0],(310,ly),(310,445)])
    path([p['LOAD'][1],(740,ly),(740,625),(310,625),(310,445)])
    path([p['LOAD_METER'][0],(785,ly),(785,570),(635,570),(635,ly)])
    path([p['LOAD_METER'][1],(930,ly),(930,625),(740,625)])
    h.shot('20_native_wired.png')
    for ref,value in [('V12','12'),('R1','4.7Meg'),('R2','47k'),('PHOTO','2.107u'),('CTRL_R','10k'),('LOAD','1k')]:
        property_value(center(p[ref]),value,ref)
    property_value(center(p['CTRL']),'IF(V(SENS)>5,9.995,0)','CTRL')
    property_value(center(p['KEY']),'IF(V(GDRV)>5,1000,1e-9)*(V(MAINS)-V(SW))','KEY')
    property_value(center(p['AC']),'220','AC')
    if not h.set_value(*center(p['AC']),'50','Hz'):raise RuntimeError('AC frequency could not be set to 50 Hz')
    set_meter_ac(center(p['LOAD_METER']))
    h.shot('30_native_values.png')
    save_final_as()
    subprocess.run(['taskkill','/IM','Multisim.exe','/T','/F'],check=False);time.sleep(3)
    subprocess.Popen([str(h.MULTISIM),str(h.TARGET)]);time.sleep(15);dismiss_reminders();h.focus()
    if '7330744_PhotoRelay_V6' not in h.mainwin().window_text():raise RuntimeError('Saved filename not present in reopened title')
    run_capture('Multisim_Light.png')
    property_value(center(p['PHOTO']),'1.475u','PHOTO_threshold');run_capture('Multisim_Threshold.png')
    property_value(center(p['PHOTO']),'0.3025u','PHOTO_dark');run_capture('Multisim_Dark.png')
    property_value(center(p['PHOTO']),'2.107u','PHOTO_return_light');h.focus();pg.hotkey('ctrl','s');time.sleep(3)
    (h.OUT/'native_validation.json').write_text(json.dumps({'native_gui_placement':True,'native_wire':True,'save_close_reopen_run_attempted':True,'size_bytes':h.TARGET.stat().st_size,'model':'Functional equivalents. Screenshot and numeric results require review.'},indent=2))
    return 0

if __name__=='__main__':
    try:sys.exit(main())
    except Exception:
        h.log(traceback.format_exc());h.shot('99_native_exception.png')
        try:save_partial()
        except Exception:h.log('Partial native save failed: '+traceback.format_exc())
        sys.exit(1)
