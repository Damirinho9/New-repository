"""Read-only inspection of the recovered Stage 10 Altium files.

This is an independent geometry check, not Altium ERC or DRC.
Requires olefile. Usage: python audit_stage10.py [input_directory] [output_directory]
"""
import csv
import hashlib
import json
import math
import struct
import sys
from collections import Counter
from pathlib import Path
import olefile

BASE = Path(sys.argv[1] if len(sys.argv)>1 else '02_Altium')
OUT = Path(sys.argv[2] if len(sys.argv)>2 else 'Проверка')
OUT.mkdir(parents=True, exist_ok=True)

def strings(data):
    offset = 0
    while offset < len(data):
        size = struct.unpack_from('<I', data, offset)[0]
        offset += 4
        raw = data[offset:offset+size]
        if len(raw) != size:
            raise ValueError('Truncated string record')
        offset += size
        yield dict(item.split('=', 1) for item in raw.rstrip(b'\0').decode('cp1252').split('|') if '=' in item)

def orient(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])

def point_segment_distance(p, a, b):
    dx, dy = b[0]-a[0], b[1]-a[1]
    den = dx*dx + dy*dy
    t = max(0, min(1, ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/den)) if den else 0
    return math.hypot(p[0]-a[0]-t*dx, p[1]-a[1]-t*dy)

def segment_distance(a, b, c, d):
    if orient(a,b,c)*orient(a,b,d) < 0 and orient(c,d,a)*orient(c,d,b) < 0:
        return 0.0
    return min(point_segment_distance(a,c,d), point_segment_distance(b,c,d), point_segment_distance(c,a,b), point_segment_distance(d,a,b))

pcb = olefile.OleFileIO(BASE/'PhotoRelay_V6.PcbDoc')
nets = {int(row['ID']): row['NAME'] for row in strings(pcb.openstream('Nets6/Data').read())}
counts = {}
for table in ['Components6','Pads6','Tracks6','Vias6','Polygons6','Nets6','ComponentBodies6','ShapeBasedComponentBodies6']:
    counts[table] = struct.unpack('<I', pcb.openstream(table+'/Header').read()[:4])[0]
tracks = []
data = pcb.openstream('Tracks6/Data').read()
offset = 0
layers = Counter()
record_index = 0
while offset < len(data):
    object_type = data[offset]
    size = struct.unpack_from('<I',data,offset+1)[0]
    row = data[offset+5:offset+5+size]
    if len(row) != size or object_type != 4 or size != 35:
        raise ValueError('Unexpected track record layout')
    offset += 5+size
    layers[row[0]] += 1
    if row[0] in (1,32):
        x1,y1,x2,y2,width = [v/393700.7874015748 for v in struct.unpack_from('<iiiiI',row,13)]
        tracks.append({'record_index_0':record_index,'layer':'Top' if row[0]==1 else 'Bottom','net':nets[struct.unpack_from('<H',row,3)[0]],'start':(x1,y1),'end':(x2,y2),'width_mm':width})
    record_index += 1

conflicts=[]
for index, a in enumerate(tracks):
    for b in tracks[:index]:
        if a['layer'] != b['layer'] or a['net'] == b['net']:
            continue
        distance=segment_distance(a['start'],a['end'],b['start'],b['end'])
        overlap=(a['width_mm']+b['width_mm'])/2-distance
        if overlap > 1e-5:
            conflicts.append({'layer':a['layer'],'record_a_0':a['record_index_0'],'net_a':a['net'],'a_start_mm':a['start'],'a_end_mm':a['end'],'a_width_mm':a['width_mm'],'record_b_0':b['record_index_0'],'net_b':b['net'],'b_start_mm':b['start'],'b_end_mm':b['end'],'b_width_mm':b['width_mm'],'centerline_distance_mm':round(distance,6),'copper_overlap_mm':round(overlap,6)})
with (OUT/'7330744_Пересечения_меди.csv').open('w',encoding='utf-8-sig',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(conflicts[0]) if conflicts else ['layer','net_a','net_b','record_a_0','record_b_0']);writer.writeheader();writer.writerows(conflicts)

sch=olefile.OleFileIO(BASE/'PhotoRelay_V6.SchDoc')
records=list(strings(sch.openstream('FileHeader').read()))
pins=[r for r in records if r.get('RECORD')=='2']
components=[r for r in records if r.get('RECORD')=='1']
source=json.loads((BASE/'PhotoRelay_V6.circuit.json').read_text())
source_ports={r['source_port_id']:r for r in source if r['type']=='source_port'}
pin_rows=[]
for trace in [r for r in source if r['type']=='source_trace']:
    for port_id in trace['connected_source_port_ids']:
        p=source_ports[port_id]
        pin_rows.append({'component':p['source_component_id'].removeprefix('sc_'),'logical_pin':p['pin_number'],'pin_name':p['name'],'net':trace['name'],'physical_pinout_verified':'NO'})
with (OUT/'7330744_Логические_выводы_и_сети.csv').open('w',encoding='utf-8-sig',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(pin_rows[0]));writer.writeheader();writer.writerows(pin_rows)
result={
 'baseline_commit':'e3198c48f355f25492ca6d01c1468f12c12f3f94',
 'binary_counts':counts,'track_layers':dict(layers),
 'same_layer_track_copper_overlap_pairs':len(conflicts),
 'rules6_present':pcb.exists('Rules6/Data'),
 'native_altium_erc_performed':False,'native_altium_drc_performed':False,
 'scope':'Independent check of binary copper track geometry, not Altium DRC',
}
baseline_path=Path(sys.argv[3]) if len(sys.argv)>3 else None
if baseline_path:
 baseline=json.loads(baseline_path.read_text())
 for kind in ['pcb_component','pcb_port','pcb_smtpad','pcb_board']:
  assert [e for e in baseline if e['type']==kind]==[e for e in source if e['type']==kind],kind+' changed'
 for v in [e for e in baseline if e['type']=='pcb_via']:
  assert v in source,'Existing via changed'
 result['component_placement_preserved']=True
 for kind in ['pcb_plated_hole']:
  old=[e for e in baseline if e['type']==kind and e.get('pcb_component_id') not in ('pcb_VT1','pcb_VT2','pcb_VD6')]
  new=[e for e in source if e['type']==kind and e.get('pcb_component_id') not in ('pcb_VT1','pcb_VT2','pcb_VD6')]
  assert old==new,'Unrelated pads changed'
 result['unrelated_pad_geometry_preserved']=True
 result['reviewed_pad_corrections']=['VT1','VT2','VD6']
 result['baseline_vias_preserved']=True
(OUT/'binary-geometry.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
assert len(conflicts)==0, 'Copper overlap filter failed'
