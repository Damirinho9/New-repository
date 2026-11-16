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
    # Datasheet-fit model, not a manufacturer macro-model.
    # ZVN2120: VGS(th)=1..3 V, RDS(on)<=10 ohm @ VGS=10 V.
    return (
        f'.SUBCKT {m} 1 2 3\n'
        'RD 1 4 2\n'
        'RS 5 3 2\n'
        'RG 2 6 20\n'
        'M1 4 6 5 5 MZVN\n'
        'D1 3 1 DBODY\n'
        '.MODEL MZVN NMOS LEVEL=1 VTO=1.10 KP=0.025 LAMBDA=0.005 CGSO=35p CGDO=7p\n'
        '.MODEL DBODY D IS=1e-12 N=1.2 BV=200 IBV=1m\n'
        f'.ENDS {m}'
    )

def _kp707v2(m):
    # Datasheet-fit model, not a manufacturer macro-model.
    # KP707V2: VGS(th) typ 3.5 V, gfs>=1.5 A/V, RDS(on)<=2.3..2.8 ohm.
    return (
        f'.SUBCKT {m} 1 2 3\n'
        'RD 1 4 0.45\n'
        'RS 5 3 0.45\n'
        'RG 2 6 10\n'
        'M1 4 6 5 5 MKP707\n'
        'D1 3 1 DBODY\n'
        '.MODEL MKP707 NMOS LEVEL=1 VTO=3.50 KP=0.40 LAMBDA=0.003 CGSO=600p CGDO=80p\n'
        '.MODEL DBODY D IS=1e-10 N=1.2 BV=700 IBV=1m\n'
        f'.ENDS {m}'
    )

def patch_models(root, xmlio):
    for ref in ('VT1', 'VT2'):
        comp = _find_component(root, xmlio, ref)
        _replace_card(_find_model(root, comp), xmlio, _zvn2120)
    comp = _find_component(root, xmlio, 'VT3')
    _replace_card(_find_model(root, comp), xmlio, _kp707v2)
    return {
        'VT1': 'KP501A -> ZVN2120 datasheet-fit VTO=1.10V',
        'VT2': 'KP501A -> ZVN2120 datasheet-fit VTO=1.10V',
        'VT3': 'KP707V2 datasheet-fit VTO=3.50V',
    }
