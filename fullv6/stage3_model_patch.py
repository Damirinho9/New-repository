def _find_component(root, xmlio, ref):
    for item in root.iter('Item'):
        if item.get('Class') == 'CiComponent' and len(item):
            name = xmlio.text(item[0].get('LocalName') or '').strip()
            if name == ref:
                return item[0]
    raise RuntimeError(f'{ref}: component not found')

def _find_model(root, comp):
    mid = comp.get('Model')
    for item in root.iter('Item'):
        if item.get('Class') == 'CiModel' and item.get('CiID') == mid and len(item):
            return item[0]
    raise RuntimeError('model not found for component')

def _replace_card(model, xmlio, body_factory):
    mname = xmlio.text(model.get('LocalName') or '').strip()
    target = None
    for el in model.iter('CiaCString'):
        txt = xmlio.text(el.get('String') or '')
        if '.SUBCKT' in txt.upper() or '.MODEL' in txt.upper():
            target = el
            break
    if target is None:
        raise RuntimeError(f'{mname}: SPICE card not found')
    target.set('String', xmlio.asc(body_factory(mname)))
    model.set('ChangedByUser', '1')

def _zvn2120(m):
    return (
        f'.SUBCKT {m} 1 2 3\n'
        'RD 1 4 2\nRS 5 3 2\nRG 2 6 20\n'
        'M1 4 6 5 5 MZVN\nD1 3 1 DBODY\n'
        '.MODEL MZVN NMOS LEVEL=1 VTO=1.00 KP=0.08 LAMBDA=0.005 CGSO=35p CGDO=7p\n'
        '.MODEL DBODY D IS=1e-12 N=1.2 BV=240 IBV=1m\n'
        f'.ENDS {m}'
    )

def _kp707v2(m):
    return (
        f'.SUBCKT {m} 1 2 3\n'
        'RD 1 4 0.35\nRS 5 3 0.35\nRG 2 6 10\n'
        'M1 4 6 5 5 MKP707\nD1 3 1 DBODY\n'
        '.MODEL MKP707 NMOS LEVEL=1 VTO=3.20 KP=0.55 LAMBDA=0.003 CGSO=600p CGDO=80p\n'
        '.MODEL DBODY D IS=1e-10 N=1.2 BV=800 IBV=1m\n'
        f'.ENDS {m}'
    )

def _t123_250(m):
    return (
        f'.SUBCKT {m} Anode Cathode Gate PARAMS: Vth=2.5 Ih=0 Vfscr=1 Ron=20m Roff=100meg\n'
        'ECTRL CTRL 0 Gate Cathode 1\n'
        'SMAIN Anode X CTRL 0 SWTH\n'
        'DMAIN X Cathode DFW\n'
        'RGK Gate Cathode 1k\n'
        '.MODEL SWTH SW(Ron={Ron} Roff={Roff} Vt=2.0 Vh=0.25)\n'
        '.MODEL DFW D(IS=1e-12 N=1 RS=20m BV=1800 IBV=1m)\n'
        f'.ENDS {m}'
    )

def patch_models(root, xmlio):
    notes={}
    for ref in ('VT1','VT2'):
        comp=_find_component(root,xmlio,ref); _replace_card(_find_model(root,comp),xmlio,_zvn2120)
        notes[ref]='KP501A -> ZVN2120 datasheet-fit, VTO=1.00 V'
    comp=_find_component(root,xmlio,'VT3'); _replace_card(_find_model(root,comp),xmlio,_kp707v2)
    notes['VT3']='KP707V2 datasheet-fit N-MOS, VTO=3.20 V'
    for ref in ('VS1','VS2'):
        comp=_find_component(root,xmlio,ref); _replace_card(_find_model(root,comp),xmlio,_t123_250)
        notes[ref]='T123-250 functional SCR; trigger referenced to cathode, VGT~2 V'
    return notes
