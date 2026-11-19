import os

def _find_component(root, xmlio, ref):
    for item in root.iter('Item'):
        if item.get('Class') == 'CiComponent' and len(item):
            if xmlio.text(item[0].get('LocalName') or '').strip() == ref:
                return item[0]
    raise RuntimeError(f'{ref}: component not found')

def _find_model(root, comp):
    mid=comp.get('Model')
    for item in root.iter('Item'):
        if item.get('Class')=='CiModel' and item.get('CiID')==mid and len(item):
            return item[0]
    raise RuntimeError('model not found')

def _replace_card(model,xmlio,factory):
    mname=xmlio.text(model.get('LocalName') or '').strip()
    target=next((e for e in model.iter('CiaCString') if '.SUBCKT' in xmlio.text(e.get('String') or '').upper() or '.MODEL' in xmlio.text(e.get('String') or '').upper()),None)
    if target is None: raise RuntimeError(f'{mname}: SPICE card absent')
    target.set('String',xmlio.asc(factory(mname))); model.set('ChangedByUser','1')

def _zvn(m):
    v=float(os.environ.get('KP501_VTO','1.5'))
    return f'.SUBCKT {m} 1 2 3\nRD 1 4 2\nRS 5 3 2\nRG 2 6 20\nM1 4 6 5 5 MZVN\nD1 3 1 DBODY\n.MODEL MZVN NMOS LEVEL=1 VTO={v:.6g} KP=0.08 LAMBDA=0.005 CGSO=35p CGDO=7p\n.MODEL DBODY D IS=1e-12 N=1.2 BV=240 IBV=1m\n.ENDS {m}'

def _kp707(m):
    v=float(os.environ.get('KP707_VTO','3.2'))
    return f'.SUBCKT {m} 1 2 3\nRD 1 4 0.35\nRS 5 3 0.35\nRG 2 6 10\nM1 4 6 5 5 MKP707\nD1 3 1 DBODY\n.MODEL MKP707 NMOS LEVEL=1 VTO={v:.6g} KP=0.55 LAMBDA=0.003 CGSO=600p CGDO=80p\n.MODEL DBODY D IS=1e-10 N=1.2 BV=800 IBV=1m\n.ENDS {m}'

def _scr_gk(m):
    v=float(os.environ.get('SCR_VTH','2.5'))
    return (
        f'.SUBCKT {m} Anode Cathode Gate PARAMS: Vth={v:.6g} Ih=0 Vfscr=1 Ron=10m Roff=100meg\\n'
        'SMAIN Anode X Gate Cathode SW_T123\\n'
        'DMAIN X Cathode D_T123\\n'
        'RGK Gate Cathode 100k\\n'
        f'.MODEL SW_T123 SW(Ron=0.01 Roff=100meg Vt={v:.6g} Vh=0.10)\\n'
        '.MODEL D_T123 D(IS=1e-10 N=1 RS=0.01 BV=1200 IBV=1m)\\n'
        f'.ENDS {m}'
    )

def _scr_vth(comp,xmlio,v):
    p=comp.find('.//CiaParamList'); ds=p.findall('./doubles/Item'); ps=p.findall('./parameters/Item')
    ds[1].set('Value',format(v,'.17g')); ps[1].set('Value',xmlio.asc(f'{v:g}'))

def patch_models(root,xmlio):
    notes={}; k=float(os.environ.get('KP501_VTO','1.5')); p=float(os.environ.get('KP707_VTO','3.2'))
    for ref in ('VT1','VT2'):
        c=_find_component(root,xmlio,ref); _replace_card(_find_model(root,c),xmlio,_zvn); notes[ref]=f'KP501A datasheet-fit N-MOS VTO={k:g}V'
    c=_find_component(root,xmlio,'VT3'); _replace_card(_find_model(root,c),xmlio,_kp707); notes['VT3']=f'KP707V2 datasheet-fit N-MOS VTO={p:g}V'
    sv=float(os.environ.get('SCR_VTH','2.5'))
    for ref in ('VS1','VS2'):
        c=_find_component(root,xmlio,ref)
        _replace_card(_find_model(root,c),xmlio,_scr_gk)
        _scr_vth(c,xmlio,sv)
        notes[ref]=f'T123-250 -> native SCR symbol/pins with functional Gate-Cathode switch model, VGT={sv:g}V'
    return notes
