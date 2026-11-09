"""Read vendor supplied PCB templates, without editing any design or license."""
import json,struct,sys
from pathlib import Path
import olefile

out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
inventory=[]
for root in [Path('C:/AD26Docs'),Path('C:/AD26/Templates'),Path('C:/Users/Public/Documents/Altium')]:
    if not root.exists():continue
    for p in root.rglob('*'):
        if p.suffix.lower() not in ['.pcbdoc','.pcbdot']:continue
        if len(inventory)>=80:break
        row={'path':str(p),'size':p.stat().st_size}
        try:
            o=olefile.OleFileIO(p)
            row['rules6_present']=o.exists('Rules6/Data')
            if row['rules6_present']:
                data=o.openstream('Rules6/Data').read()
                row['rules_data_bytes']=len(data)
                row['rules_header_hex']=o.openstream('Rules6/Header').read().hex()
                n=len(inventory)
                (out/f'{n:02d}_Rules6_Data.bin').write_bytes(data)
                (out/f'{n:02d}_Rules6_Header.bin').write_bytes(o.openstream('Rules6/Header').read())
                (out/f'{n:02d}_Rules6_Decoded.txt').write_text(data.decode('cp1252',errors='replace'),encoding='utf-8')
        except Exception as e:row['error']=str(e)
        inventory.append(row)
(out/'vendor-template-inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
print(json.dumps(inventory,indent=2))
