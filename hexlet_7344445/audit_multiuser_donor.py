from pathlib import Path
from ptlab import codec
import json, os, re, hashlib

ROOT = Path(os.environ.get("DONOR_DIR","/tmp/ccna"))
OUT = Path("hexlet_7344445/multiuser_audit")
OUT.mkdir(parents=True, exist_ok=True)

paths = [
ROOT/"1.Intro/Packet Tracer PKA Source Files/10.4.1.2 Packet Tracer Multiuser - Tutorial - Client Side.pka",
ROOT/"1.Intro/Packet Tracer PKA Source Files/10.4.1.2 Packet Tracer Multiuser - Tutorial - Server Side.pka",
]
rows=[]
for p in paths:
    raw=codec.decode(p)
    text=raw.decode("utf-8",errors="replace")
    item={"file":p.name,"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"root":""}
    mroot=re.search(r"<([A-Z0-9_]+)", text)
    item["root"]=mroot.group(1) if mroot else ""
    for tag in ("MULTIUSER","REMOTE_NETWORKS","REMOTE_NETWORK","IPC_MANAGER"):
        item[tag]=re.findall(fr"<{tag}\\b[^>]*>.*?</{tag}>",text,flags=re.S|re.I)
    devs=[]
    for block in re.findall(r"<DEVICE>.*?</DEVICE>",text,flags=re.S|re.I):
        mm=re.search(r'<TYPE[^>]*model="([^"]*)"',block,re.I)
        nn=re.search(r"<NAME[^>]*>(.*?)</NAME>",block,flags=re.S|re.I)
        model=mm.group(1) if mm else ""
        name=re.sub(r"<.*?>","",nn.group(1)).strip() if nn else ""
        if model or name:
            devs.append({"name":name,"model":model})
    item["devices"]=devs
    item["literals"]=sorted(set(re.findall(r"[^<>\\n]{1,120}(?:3800\\d|localhost|REMOTE_NETWORK|Multiuser|MU_|Channel\\d|PEER)[^<>\\n]{0,120}",text,re.I)))
    rows.append(item)
    (OUT/(p.stem+".xml")).write_bytes(raw)

(OUT/"audit.json").write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8")
for item in rows:
    print("FILE",item["file"],"root",item["root"],"devices",len(item["devices"]))
    print("MODELS",sorted(set(d["model"] for d in item["devices"] if d["model"])))
    for tag in ("MULTIUSER","REMOTE_NETWORKS","REMOTE_NETWORK","IPC_MANAGER"):
        print(tag,"count",len(item[tag]))
        for block in item[tag][:3]:
            print(block[:5000])
    print("LITERALS")
    for s in item["literals"][:100]:
        print(" ",s)
