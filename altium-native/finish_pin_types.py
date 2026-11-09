import sys,struct,re,json,hashlib
from pathlib import Path
import olefile
base=Path(sys.argv[1]);path=base/'PhotoRelay_V6.SchDoc'
o=olefile.OleFileIO(path,write_mode=True);raw=o.openstream('FileHeader').read();buf=bytearray(raw);offset=0;gate_count=0
while offset<len(raw):
 size=struct.unpack_from('<I',raw,offset)[0];start=offset+4;body=raw[start:start+size];offset=start+size
 if b'|RECORD=2|' in body and re.search(rb'\|NAME=G(?:\||\x00)',body):
  assert body.count(b'|ELECTRICAL=4|')==1
  buf[start:start+size]=body.replace(b'|ELECTRICAL=4|',b'|ELECTRICAL=0|');gate_count+=1
assert gate_count==5,gate_count
o.write_stream('FileHeader',bytes(buf));o.close()
# Per-component review: passive resistive/junction terminals remain Passive; only control gates Input.
review={'passive_components':['R1','R2','R3','R4','R5','R6','R7','R8','R9','C1','C2','C3','VD1','VD2','VD3','VD4','VD5','VD6','HL1','RU1','FU1','FU2','XP1'], 'gate_input_components':['VT1','VT2','VT3','VS1','VS2'], 'passive_on_controlled_devices':['D','S','A','K'],'gate_pin_input_count':gate_count,'physical_pinout_verified_components':['VT1','VT2'],'bridge_geometry_verified':'VD6 Rectron RB15 opposing AC pair and DC pair; numerical pad identifiers are library-defined','remaining_physical_pinouts_verified':False,'native_erc_performed':False}
(base/'pin-review.json').write_text(json.dumps(review,indent=2))
manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in base.iterdir() if p.suffix in ['.SchDoc','.PcbDoc','.PrjPcb'] or p.name=='PhotoRelay_V6.circuit.json'}
(base/'SHA256SUMS.json').write_text(json.dumps(manifest,indent=2))
print('Five gate pins Input; all other electrical types retained')
