from __future__ import annotations
import hashlib, json, os, re, sys
from pathlib import Path

from ptlab import codec\nfrom ptlab import lab as labfile

ROOT = Path(os.environ.get("DONOR_DIR", "/tmp/donor"))
OUT = Path(os.environ.get("OUT_DIR", "hexlet_7344445/donor_audit"))
OUT.mkdir(parents=True, exist_ok=True)

signatures = {
    "lr1_ip_4": b"192.168.0.4",
    "lr1_ip_5": b"192.168.0.5",
    "lr1_printer_ip": b"192.168.0.10",
    "lr2_server1": b"10.0.0.1",
    "lr2_server2": b"10.0.0.2",
    "lr2_alias": b"www.rambler.ru",
    "lr2_fqdn": b"server1.rambler.ru",
    "lr2_dhcp_start": b"10.0.0.10",
    "lr3_hostname_r1": b"hostname Router1",
    "lr3_enable_password": b"enable password parol",
    "lr3_description": b"Ethernet interface on Router 1",
}

rows = []
for p in sorted(ROOT.rglob("*.pkt")):
    raw = p.read_bytes()
    item = {
        "path": str(p.relative_to(ROOT)),
        "size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "decode": "FAIL",
        "devices": [],
        "models": [],
        "names": [],
        "signatures": {},
        "dns_records": [],
        "dhcp_pools": [],
        "links": [],
        "config_hits": [],
        "http_index_contains_rambler": False,
    }
    try:
        xml = codec.decode(p)
        item["decode"] = "PASS"
        text = xml.decode("utf-8", errors="replace")
        item["signatures"] = {k: (v in xml) for k, v in signatures.items()}
        dev_blocks = re.findall(r"<DEVICE>.*?</DEVICE>", text, flags=re.S)
        for block in dev_blocks:
            m = re.search(r'<TYPE[^>]*model="([^"]*)"', block)
            n = re.search(r"<NAME[^>]*>(.*?)</NAME>", block, flags=re.S)
            model = m.group(1) if m else ""
            name = re.sub(r"<.*?>", "", n.group(1)).strip() if n else ""
            item["devices"].append({"model": model, "name": name})
        item["models"] = sorted({d["model"] for d in item["devices"] if d["model"]})
        item["names"] = [d["name"] for d in item["devices"] if d["name"]]

        for rec in re.findall(r"<RESOURCE-RECORD>.*?</RESOURCE-RECORD>", text, flags=re.S):
            def tag(t):
                m = re.search(fr"<{t}[^>]*>(.*?)</{t}>", rec, flags=re.S)
                return re.sub(r"<.*?>", "", m.group(1)).strip() if m else ""
            item["dns_records"].append({
                "type": tag("TYPE"), "name": tag("NAME"),
                "ttl": tag("TTL"), "value": tag("IPADDRESS") or tag("HOSTNAME")
            })

        for pool in re.findall(r"<POOL>.*?</POOL>", text, flags=re.S):
            def ptag(t):
                m = re.search(fr"<{t}[^>]*>(.*?)</{t}>", pool, flags=re.S)
                return re.sub(r"<.*?>", "", m.group(1)).strip() if m else ""
            if any(ptag(t) for t in ("NETWORK","START_IP","DNS_SERVER")):
                item["dhcp_pools"].append({
                    "name": ptag("NAME"), "network": ptag("NETWORK"), "mask": ptag("MASK"),
                    "gateway": ptag("DEFAULT_ROUTER"), "start": ptag("START_IP"),
                    "end": ptag("END_IP"), "dns": ptag("DNS_SERVER"),
                    "max_users": ptag("MAX_USERS")
                })

        for line in re.findall(r"<LINE[^>]*>(.*?)</LINE>", text, flags=re.S):
            clean = re.sub(r"<.*?>", "", line).strip()
            if any(x.lower() in clean.lower() for x in (
                "hostname", "enable password", "description", "no shutdown", "clock rate"
            )):
                item["config_hits"].append(clean)

        item["http_index_contains_rambler"] = (
            "WWW.RAMBLER.RU" in text or "www.rambler.ru" in text
        )
    except Exception as exc:
        item["error"] = f"{type(exc).__name__}: {exc}"
    rows.append(item)

(OUT / "donor_audit.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

for r in rows:
    sig = [k for k,v in r.get("signatures",{}).items() if v]
    print(f"FILE={r['path']} decode={r['decode']} size={r['size']} models={','.join(r['models'])}")
    print("  signatures=" + ",".join(sig))
    if r["dns_records"]:
        print("  dns=" + json.dumps(r["dns_records"], ensure_ascii=False))
    if r["dhcp_pools"]:
        print("  dhcp=" + json.dumps(r["dhcp_pools"], ensure_ascii=False))
    if r["config_hits"]:
        print("  config=" + " | ".join(r["config_hits"][:30]))
    if r["http_index_contains_rambler"]:
        print("  HTTP_RAMBler=YES")
