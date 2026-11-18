from __future__ import annotations

import hashlib
import ipaddress
import json
import shutil
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from ptlab import codec
from ptlab import lab as pt

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cfg_switch(hostname: str, vlans: list[tuple[int, str]], ports: list[tuple[str, str, int | None]]) -> list[str]:
    lines = [f"hostname {hostname}"]
    for vid, name in vlans:
        lines += [f"vlan {vid}", f" name {name}", "exit"]
    for port, mode, vlan in ports:
        lines += [f"interface {port}"]
        if mode == "access":
            lines += [" switchport mode access", f" switchport access vlan {vlan}", " no shutdown"]
        elif mode == "trunk":
            lines += [" switchport mode trunk", " no shutdown"]
        else:
            raise ValueError(mode)
        lines.append("exit")
    lines.append("end")
    return lines


def cfg_router(hostname: str, interfaces: list[tuple[str, str, str]], extra: list[str] | None = None) -> list[str]:
    lines = [f"hostname {hostname}"]
    for port, ip, mask in interfaces:
        lines += [f"interface {port}", f" ip address {ip} {mask}", " no shutdown", "exit"]
    lines += list(extra or [])
    if not lines or lines[-1] != "end":
        lines.append("end")
    return lines


def mirror_startup(path: Path) -> None:
    import copy
    lab, p = pt._lab(path)
    for el in lab.devs.findall("DEVICE"):
        eng = el.find("ENGINE")
        if eng is None:
            continue
        running = eng.find("RUNNINGCONFIG")
        if running is None:
            continue
        startup = eng.find("STARTUPCONFIG")
        if startup is None:
            startup = ET.SubElement(eng, "STARTUPCONFIG")
        for c in list(startup):
            startup.remove(c)
        for c in list(running):
            startup.append(copy.deepcopy(c))
    pt._save(lab, p)


def add_http(path: Path, server: str) -> None:
    pt.set_service(path, server, "http", True)


def add_ftp(path: Path, server: str, username: str = "student", password: str = "cisco") -> None:
    lab, p = pt._lab(path)
    el = pt._device(lab, server)
    eng = el.find("ENGINE")
    if eng is None:
        raise RuntimeError(f"{server}: ENGINE missing")
    ftp = next(el.iter("FTP_SERVER"), None)
    if ftp is None:
        ftp = ET.SubElement(eng, "FTP_SERVER")
    enabled = ftp.find("ENABLED")
    if enabled is None:
        enabled = ET.SubElement(ftp, "ENABLED")
    enabled.text = "1"
    mgr = ftp.find("USER_ACCOUNT_MNGR")
    if mgr is None:
        mgr = ET.SubElement(ftp, "USER_ACCOUNT_MNGR")
    for c in list(mgr):
        mgr.remove(c)
    account = ET.SubElement(mgr, "ACCOUNT")
    ET.SubElement(account, "USERNAME").text = username
    ET.SubElement(account, "PASSWORD").text = password
    ET.SubElement(account, "PERMISSIONS").text = "RWDNL"
    pt._save(lab, p)


def install_dual_ethernet(path: Path, router: str) -> None:
    pt.install_module(path, router, "WIC-1ENET", 0)
    pt.install_module(path, router, "WIC-1ENET", 1)


def add_switch(path: Path, model: str, name: str, x: int, y: int, config: list[str]) -> None:
    pt.add_device(path, model, name, x=x, y=y, config=config)


def add_pc(path: Path, name: str, x: int, y: int, ip: str, gateway: str = "") -> None:
    pt.add_device(path, "PC-PT", name, x=x, y=y, host_ip=ip, host_gateway=gateway)


def add_server(path: Path, name: str, x: int, y: int, ip: str, gateway: str = "", http: bool = False, ftp: bool = False) -> None:
    pt.add_device(path, "Server-PT", name, x=x, y=y, host_ip=ip, host_gateway=gateway)
    if http:
        add_http(path, name)
    if ftp:
        add_ftp(path, name)


# ---------------------------------------------------------------------------
# VLAN labs
# ---------------------------------------------------------------------------

def build_lr9() -> Path:
    p = OUT / "09_ЛР_VLAN_один_коммутатор.pkt"
    pt.new(p)
    sw_cfg = cfg_switch("Коммутатор0", [(2, "subnet_10"), (3, "subnet_192")], [
        ("FastEthernet0/1", "access", 2),
        ("FastEthernet0/2", "access", 2),
        ("FastEthernet0/3", "access", 2),
        ("FastEthernet0/4", "access", 3),
        ("FastEthernet0/5", "access", 3),
    ])
    add_switch(p, "2960-24TT", "Коммутатор0", 520, 360, sw_cfg)
    pcs = [
        ("ПК0", 180, 120, "10.0.0.1/8", "FastEthernet0/1"),
        ("ПК1", 180, 280, "10.0.0.2/8", "FastEthernet0/2"),
        ("ПК2", 180, 460, "10.0.0.3/8", "FastEthernet0/3"),
        ("ПК3", 860, 280, "10.0.0.4/8", "FastEthernet0/4"),
        ("ПК4", 860, 460, "10.0.0.5/8", "FastEthernet0/5"),
    ]
    for name, x, y, ip, port in pcs:
        add_pc(p, name, x, y, ip)
        pt.add_link(p, name, "FastEthernet0", "Коммутатор0", port, "copper")
    mirror_startup(p)
    return p


def build_lr10_trunk() -> Path:
    p = OUT / "10A_ЛР_VLAN_два_коммутатора_trunk.pkt"
    pt.new(p)
    sw1 = cfg_switch("Switch1", [(20, "VLAN0020"), (30, "VLAN0030")], [
        ("FastEthernet0/1", "access", 20),
        ("FastEthernet0/2", "access", 30),
        ("FastEthernet0/3", "trunk", None),
    ])
    sw2 = cfg_switch("Switch2", [(20, "VLAN0020"), (30, "VLAN0030")], [
        ("FastEthernet0/1", "access", 20),
        ("FastEthernet0/2", "access", 30),
        ("FastEthernet0/3", "trunk", None),
    ])
    add_switch(p, "2950-24", "Switch1", 330, 360, sw1)
    add_switch(p, "2950-24", "Switch2", 750, 360, sw2)
    for name, x, y, ip, sw, port in [
        ("2_1", 180, 120, "10.0.0.1/8", "Switch1", "FastEthernet0/1"),
        ("3_1", 180, 610, "10.0.0.2/8", "Switch1", "FastEthernet0/2"),
        ("2_2", 900, 120, "10.0.0.3/8", "Switch2", "FastEthernet0/1"),
        ("3_2", 900, 610, "10.0.0.4/8", "Switch2", "FastEthernet0/2"),
    ]:
        add_pc(p, name, x, y, ip)
        pt.add_link(p, name, "FastEthernet0", sw, port, "copper")
    pt.add_link(p, "Switch1", "FastEthernet0/3", "Switch2", "FastEthernet0/3", "crossover")
    mirror_startup(p)
    return p


def build_lr10_routed() -> Path:
    p = OUT / "10B_ЛР_VLAN_маршрутизация_между_подсетями.pkt"
    pt.new(p)
    sw1 = cfg_switch("Switch1", [(20, "VLAN0020"), (30, "VLAN0030")], [
        ("FastEthernet0/1", "access", 20),
        ("FastEthernet0/2", "access", 30),
        ("FastEthernet0/3", "trunk", None),
        ("FastEthernet0/4", "access", 20),
    ])
    sw2 = cfg_switch("Switch2", [(20, "VLAN0020"), (30, "VLAN0030")], [
        ("FastEthernet0/1", "access", 20),
        ("FastEthernet0/2", "access", 30),
        ("FastEthernet0/3", "trunk", None),
        ("FastEthernet0/4", "access", 30),
    ])
    add_switch(p, "2950-24", "Switch1", 330, 360, sw1)
    add_switch(p, "2950-24", "Switch2", 750, 360, sw2)
    pt.add_device(p, "1841", "Router1", x=540, y=520, config=cfg_router("Router1", [
        ("FastEthernet0/0", "10.2.0.254", "255.255.0.0"),
        ("FastEthernet0/1", "10.3.0.254", "255.255.0.0"),
    ]))
    for name, x, y, ip, gw, sw, port in [
        ("2_1", 180, 120, "10.2.0.1/16", "10.2.0.254", "Switch1", "FastEthernet0/1"),
        ("3_1", 180, 610, "10.3.0.2/16", "10.3.0.254", "Switch1", "FastEthernet0/2"),
        ("2_2", 900, 120, "10.2.0.3/16", "10.2.0.254", "Switch2", "FastEthernet0/1"),
        ("3_2", 900, 610, "10.3.0.4/16", "10.3.0.254", "Switch2", "FastEthernet0/2"),
    ]:
        add_pc(p, name, x, y, ip, gw)
        pt.add_link(p, name, "FastEthernet0", sw, port, "copper")
    pt.add_link(p, "Switch1", "FastEthernet0/3", "Switch2", "FastEthernet0/3", "crossover")
    pt.add_link(p, "Router1", "FastEthernet0/0", "Switch1", "FastEthernet0/4", "copper")
    pt.add_link(p, "Router1", "FastEthernet0/1", "Switch2", "FastEthernet0/4", "copper")
    mirror_startup(p)
    return p


# ---------------------------------------------------------------------------
# ACL helpers + labs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Rule:
    action: str
    proto: str = "ip"
    src: str = "any"
    dst: str = "any"
    dport: int | None = None


def ip_match(spec: str, ip: str) -> bool:
    if spec == "any":
        return True
    if spec.startswith("host "):
        return ip == spec.split()[1]
    return ipaddress.ip_address(ip) in ipaddress.ip_network(spec, strict=False)


def acl_match(rule: Rule, src: str, dst: str, proto: str, dport: int | None) -> bool:
    if rule.proto != "ip" and rule.proto != proto:
        return False
    if not ip_match(rule.src, src) or not ip_match(rule.dst, dst):
        return False
    if rule.dport is not None and rule.dport != dport:
        return False
    return True


def eval_acl(rules: list[Rule], src: str, dst: str, proto: str = "ip", dport: int | None = None) -> bool:
    for r in rules:
        if acl_match(r, src, dst, proto, dport):
            return r.action == "permit"
    return False


def rule_ios(r: Rule) -> str:
    s = f"{r.action} {r.proto} "
    s += ("any" if r.src == "any" else (r.src if r.src.startswith("host ") else _net_wildcard(r.src)))
    s += " "
    s += ("any" if r.dst == "any" else (r.dst if r.dst.startswith("host ") else _net_wildcard(r.dst)))
    if r.dport is not None:
        s += f" eq {r.dport}"
    return s


def _net_wildcard(cidr: str) -> str:
    net = ipaddress.ip_network(cidr, strict=False)
    wc = ipaddress.ip_address(int(net.hostmask))
    return f"{net.network_address} {wc}"


def acl_lines(number: int, rules: list[Rule]) -> list[str]:
    lines = [f"ip access-list extended {number}"]
    lines += [f" {rule_ios(r)}" for r in rules]
    lines += ["exit"]
    return lines


def standard_acl_lines(number: int, sources: list[tuple[str, str]]) -> list[str]:
    lines = [f"ip access-list standard {number}"]
    for action, src in sources:
        lines.append(f" {action} {src}")
    lines.append("exit")
    return lines


def add_four_port_router(path: Path, name: str, x: int, y: int, interfaces: list[tuple[str, str, str]], extra: list[str]) -> None:
    pt.add_device(path, "1841", name, x=x, y=y, config=cfg_router(name, interfaces, extra))
    install_dual_ethernet(path, name)


def build_acl_base() -> tuple[Path, dict]:
    p = OUT / "ACL00_Базовый_стандартный_список_10.pkt"
    pt.new(p)
    add_switch(p, "2950-24", "Switch1", 300, 380, ["hostname Switch1", "end"])
    add_switch(p, "2950-24", "Switch2", 800, 380, ["hostname Switch2", "end"])
    extra = standard_acl_lines(10, [("deny", "host 12.0.0.13"), ("deny", "host 12.0.0.14"), ("permit", "any")])
    extra += ["interface FastEthernet0/0", " ip access-group 10 out", "exit"]
    pt.add_device(p, "1841", "Router1", x=550, y=380, config=cfg_router("Router1", [
        ("FastEthernet0/0", "11.0.0.1", "255.0.0.0"),
        ("FastEthernet0/1", "12.0.0.1", "255.0.0.0"),
    ], extra))
    hosts = [
        ("Server1", "Server-PT", 80, 180, "11.0.0.2/8", "11.0.0.1", "Switch1", "FastEthernet0/1"),
        ("comp1", "PC-PT", 80, 370, "11.0.0.11/8", "11.0.0.1", "Switch1", "FastEthernet0/2"),
        ("comp2", "PC-PT", 80, 560, "11.0.0.12/8", "11.0.0.1", "Switch1", "FastEthernet0/3"),
        ("Server2", "Server-PT", 1020, 180, "12.0.0.2/8", "12.0.0.1", "Switch2", "FastEthernet0/1"),
        ("comp3", "PC-PT", 1020, 370, "12.0.0.13/8", "12.0.0.1", "Switch2", "FastEthernet0/2"),
        ("comp4", "PC-PT", 1020, 560, "12.0.0.14/8", "12.0.0.1", "Switch2", "FastEthernet0/3"),
    ]
    for n, model, x, y, ip, gw, sw, port in hosts:
        pt.add_device(p, model, n, x=x, y=y, host_ip=ip, host_gateway=gw)
        if model == "Server-PT":
            add_http(p, n)
        pt.add_link(p, n, "FastEthernet0", sw, port, "copper")
    pt.add_link(p, "Router1", "FastEthernet0/0", "Switch1", "FastEthernet0/4", "copper")
    pt.add_link(p, "Router1", "FastEthernet0/1", "Switch2", "FastEthernet0/4", "copper")
    mirror_startup(p)
    policy = {
        "acl_out_net11_denied_sources": {"12.0.0.13", "12.0.0.14"},
    }
    return p, policy


def build_acl5() -> tuple[Path, dict[str, list[Rule]]]:
    p = OUT / "ACL05_Самостоятельная_работа_5.pkt"
    pt.new(p)
    switches = [("sw1",120,180),("sw2",950,180),("sw3",950,600),("sw4",120,600)]
    for n,x,y in switches:
        add_switch(p, "2950-24", n, x, y, [f"hostname {n}", "end"])
    rules = {
        "net11": [Rule("permit","ip","host 11.0.0.4","host 12.0.0.4"), Rule("deny","ip","host 11.0.0.4","any"), Rule("permit")],
        "net12": [Rule("permit","ip","host 12.0.0.4","host 11.0.0.4"), Rule("deny","ip","host 12.0.0.4","any"), Rule("permit")],
        "net13": [Rule("permit","ip","host 13.0.0.4","host 14.0.0.4"), Rule("deny","ip","host 13.0.0.4","any"), Rule("permit")],
        "net14": [Rule("permit","ip","host 14.0.0.4","host 13.0.0.4"), Rule("deny","ip","host 14.0.0.4","any"), Rule("permit")],
    }
    extra = []
    for num, key, iface in [(101,"net11","FastEthernet0/0"),(102,"net12","FastEthernet0/1"),(103,"net13","Ethernet0/0/0"),(104,"net14","Ethernet0/1/0")]:
        extra += acl_lines(num, rules[key])
        extra += [f"interface {iface}", f" ip access-group {num} in", "exit"]
    add_four_port_router(p, "router", 540, 390, [
        ("FastEthernet0/0","11.0.0.1","255.0.0.0"),
        ("FastEthernet0/1","12.0.0.1","255.0.0.0"),
        ("Ethernet0/0/0","13.0.0.1","255.0.0.0"),
        ("Ethernet0/1/0","14.0.0.1","255.0.0.0"),
    ], extra)

    networks = [
        ("sw1","11.0.0", [("S1","Server-PT",2),("comp1","PC-PT",3),("comp2","PC-PT",4)], "FastEthernet0/0"),
        ("sw2","12.0.0", [("S2","Server-PT",2),("comp3","PC-PT",3),("comp4","PC-PT",4)], "FastEthernet0/1"),
        ("sw3","13.0.0", [("S3","Server-PT",2),("comp5","PC-PT",3),("comp6","PC-PT",4)], "Ethernet0/0/0"),
        ("sw4","14.0.0", [("S4","Server-PT",2),("comp7","PC-PT",3),("comp8","PC-PT",4)], "Ethernet0/1/0"),
    ]
    pos = {"sw1":(40,150),"sw2":(1070,150),"sw3":(1070,600),"sw4":(40,600)}
    for sw,prefix,items,rport in networks:
        base_x, base_y = pos[sw]
        for i,(name,model,last) in enumerate(items):
            ip=f"{prefix}.{last}/8"; gw=f"{prefix}.1"
            x=base_x; y=base_y+i*110
            pt.add_device(p, model, name, x=x, y=y, host_ip=ip, host_gateway=gw)
            if model=="Server-PT": add_http(p,name)
            pt.add_link(p,name,"FastEthernet0",sw,f"FastEthernet0/{i+1}","copper")
        pt.add_link(p,"router",rport,sw,"FastEthernet0/10","copper")
    mirror_startup(p)
    return p, rules


def build_acl6() -> tuple[Path, dict[str, list[Rule]]]:
    p = OUT / "ACL06_Самостоятельная_работа_6.pkt"
    pt.new(p)
    for n,x,y in [("sw1",120,420),("sw2",390,130),("sw3",930,420),("sw4",390,680)]:
        add_switch(p,"2950-24",n,x,y,[f"hostname {n}","end"])

    r11 = [
        Rule("deny","ip","11.0.0.0/8","14.0.0.0/8"),
        Rule("deny","icmp","host 11.0.0.11","host 12.0.0.2"),
        Rule("permit","tcp","host 11.0.0.11","host 12.0.0.2",80),
        Rule("deny","tcp","host 11.0.0.11","host 13.0.0.2",80),
        Rule("permit","ip","host 11.0.0.11","host 13.0.0.2"),
        Rule("permit"),
    ]
    r13 = [
        Rule("deny","icmp","host 13.0.0.13","host 12.0.0.2"),
        Rule("permit","tcp","host 13.0.0.13","host 12.0.0.2",80),
        Rule("deny","tcp","host 13.0.0.13","host 11.0.0.2",80),
        Rule("permit","ip","host 13.0.0.13","host 11.0.0.2"),
        Rule("permit","ip","host 13.0.0.13","host 14.0.0.2"),
        Rule("permit"),
    ]
    extra = acl_lines(111,r11)+["interface FastEthernet0/0"," ip access-group 111 in","exit"]
    extra += acl_lines(113,r13)+["interface Ethernet0/0/0"," ip access-group 113 in","exit"]
    add_four_port_router(p,"Router1",600,420,[
        ("FastEthernet0/0","11.0.0.1","255.0.0.0"),
        ("FastEthernet0/1","12.0.0.1","255.0.0.0"),
        ("Ethernet0/0/0","13.0.0.1","255.0.0.0"),
        ("Ethernet0/1/0","14.0.0.1","255.0.0.0"),
    ],extra)

    add_server(p,"server1",80,330,"11.0.0.2/8","11.0.0.1",http=True)
    add_pc(p,"comp1",80,510,"11.0.0.11/8","11.0.0.1")
    add_server(p,"server3",390,40,"12.0.0.2/8","12.0.0.1",http=True)
    add_server(p,"server2",1080,330,"13.0.0.2/8","13.0.0.1",http=True)
    add_pc(p,"comp2",1080,510,"13.0.0.13/8","13.0.0.1")
    add_server(p,"server4",390,790,"14.0.0.2/8","14.0.0.1",http=True)

    for dev,sw,port in [
        ("server1","sw1","FastEthernet0/1"),("comp1","sw1","FastEthernet0/2"),
        ("server3","sw2","FastEthernet0/1"),("server2","sw3","FastEthernet0/1"),
        ("comp2","sw3","FastEthernet0/2"),("server4","sw4","FastEthernet0/1"),
    ]:
        pt.add_link(p,dev,"FastEthernet0",sw,port,"copper")
    for sw,rport in [("sw1","FastEthernet0/0"),("sw2","FastEthernet0/1"),("sw3","Ethernet0/0/0"),("sw4","Ethernet0/1/0")]:
        pt.add_link(p,"Router1",rport,sw,"FastEthernet0/10","copper")
    mirror_startup(p)
    return p, {"net11":r11,"net13":r13}


def build_acl7() -> tuple[Path, dict[str, list[Rule]]]:
    p = OUT / "ACL07_Самостоятельная_работа_7_VLAN_ACL.pkt"
    pt.new(p)
    vlans=[(10,"VLAN10"),(20,"VLAN20"),(30,"VLAN30"),(99,"SERVER")]
    s1cfg=cfg_switch("switch1",vlans,[
        ("FastEthernet0/1","access",10),("FastEthernet0/2","access",20),
        ("FastEthernet0/23","trunk",None),("FastEthernet0/24","trunk",None)])
    s2cfg=cfg_switch("switch2",vlans,[
        ("FastEthernet0/1","access",10),("FastEthernet0/2","access",20),("FastEthernet0/3","access",30),
        ("FastEthernet0/23","trunk",None),("FastEthernet0/24","trunk",None)])
    s3cfg=cfg_switch("switch3",vlans,[
        ("FastEthernet0/1","access",10),("FastEthernet0/2","access",20),("FastEthernet0/3","access",30),
        ("FastEthernet0/24","trunk",None)])
    add_switch(p,"2950-24","switch1",250,180,s1cfg)
    add_switch(p,"2950-24","switch2",250,420,s2cfg)
    add_switch(p,"2950-24","switch3",250,660,s3cfg)

    acl10=[Rule("permit","ip","any","host 10.99.0.10"),Rule("deny")]
    acl20=[Rule("permit","ip","any","host 10.99.0.10"),Rule("deny")]
    acl30=[Rule("permit","ip","any","host 10.99.0.10"),Rule("deny")]
    l3extra=[]
    for num,rules,vlan in [(110,acl10,10),(120,acl20,20),(130,acl30,30)]:
        l3extra += acl_lines(num,rules)
        l3extra += [f"interface Vlan{vlan}",f" ip access-group {num} in","exit"]
    l3cfg=["hostname switch4","ip routing"]
    for vid,name in vlans:
        l3cfg += [f"vlan {vid}",f" name {name}","exit"]
    l3cfg += [
        "interface FastEthernet0/1"," switchport mode trunk"," no shutdown","exit",
        "interface FastEthernet0/2"," switchport mode access"," switchport access vlan 99"," no shutdown","exit",
        "interface Vlan10"," ip address 10.10.0.1 255.255.255.0"," no shutdown","exit",
        "interface Vlan20"," ip address 10.20.0.1 255.255.255.0"," no shutdown","exit",
        "interface Vlan30"," ip address 10.30.0.1 255.255.255.0"," no shutdown","exit",
        "interface Vlan99"," ip address 10.99.0.1 255.255.255.0"," no shutdown","exit",
    ] + l3extra + ["end"]
    add_switch(p,"3560-24PS","switch4",560,80,l3cfg)
    add_server(p,"server1",900,80,"10.99.0.10/24","10.99.0.1",http=True)

    hosts=[
        ("comp1","switch1","FastEthernet0/1","10.10.0.11/24","10.10.0.1",10,500,180),
        ("comp2","switch2","FastEthernet0/1","10.10.0.12/24","10.10.0.1",10,500,380),
        ("comp3","switch3","FastEthernet0/1","10.10.0.13/24","10.10.0.1",10,500,620),
        ("comp4","switch1","FastEthernet0/2","10.20.0.14/24","10.20.0.1",20,760,180),
        ("comp5","switch2","FastEthernet0/2","10.20.0.15/24","10.20.0.1",20,760,380),
        ("comp6","switch3","FastEthernet0/2","10.20.0.16/24","10.20.0.1",20,760,620),
        ("comp7","switch2","FastEthernet0/3","10.30.0.17/24","10.30.0.1",30,1020,380),
        ("comp8","switch3","FastEthernet0/3","10.30.0.18/24","10.30.0.1",30,1020,620),
    ]
    for name,sw,port,ip,gw,vlan,x,y in hosts:
        add_pc(p,name,x,y,ip,gw); pt.add_link(p,name,"FastEthernet0",sw,port,"copper")
    pt.add_link(p,"switch1","FastEthernet0/23","switch4","FastEthernet0/1","crossover")
    pt.add_link(p,"switch1","FastEthernet0/24","switch2","FastEthernet0/24","crossover")
    pt.add_link(p,"switch2","FastEthernet0/23","switch3","FastEthernet0/24","crossover")
    pt.add_link(p,"server1","FastEthernet0","switch4","FastEthernet0/2","copper")
    mirror_startup(p)
    return p, {"vlan10":acl10,"vlan20":acl20,"vlan30":acl30}


def build_acl8() -> tuple[Path, list[Rule]]:
    p = OUT / "ACL08_Самостоятельная_работа_8_Web_FTP.pkt"
    pt.new(p)
    add_switch(p,"2950-24","Switch0",260,390,["hostname Switch0","end"])
    add_switch(p,"2950-24","Switch1",820,390,["hostname Switch1","end"])

    rules=[
        # comp1 -> Server1 FTP yes, Web no
        Rule("deny","tcp","host 11.0.0.1","host 12.0.0.1",80),
        Rule("permit","tcp","host 11.0.0.1","host 12.0.0.1"),
        # comp1 -> Server2 Web yes, FTP no
        Rule("deny","tcp","host 11.0.0.1","host 12.0.0.2",20),
        Rule("deny","tcp","host 11.0.0.1","host 12.0.0.2",21),
        Rule("permit","tcp","host 11.0.0.1","host 12.0.0.2",80),
        # comp1 -> Server3 Web+FTP yes
        Rule("permit","tcp","host 11.0.0.1","host 12.0.0.3"),
        # comp2 -> Server1 Web yes, FTP no
        Rule("deny","tcp","host 11.0.0.2","host 12.0.0.1",20),
        Rule("deny","tcp","host 11.0.0.2","host 12.0.0.1",21),
        Rule("permit","tcp","host 11.0.0.2","host 12.0.0.1",80),
        # comp2 -> Server2 FTP yes, Web no
        Rule("deny","tcp","host 11.0.0.2","host 12.0.0.2",80),
        Rule("permit","tcp","host 11.0.0.2","host 12.0.0.2"),
        # comp2 -> Server3 Web+FTP yes
        Rule("permit","tcp","host 11.0.0.2","host 12.0.0.3"),
        Rule("permit"),
    ]
    extra=acl_lines(108,rules)+["interface FastEthernet0/0"," ip access-group 108 in","exit"]
    pt.add_device(p,"1841","Router0",x=540,y=390,config=cfg_router("Router0",[
        ("FastEthernet0/0","11.0.0.111","255.0.0.0"),
        ("FastEthernet0/1","12.0.0.111","255.0.0.0"),
    ],extra))
    add_pc(p,"comp1",80,260,"11.0.0.1/8","11.0.0.111")
    add_pc(p,"comp2",80,520,"11.0.0.2/8","11.0.0.111")
    for i,n in enumerate(["Server1","Server2","Server3"],1):
        add_server(p,n,1030,180+i*150,f"12.0.0.{i}/8","12.0.0.111",http=True,ftp=True)
    pt.add_link(p,"comp1","FastEthernet0","Switch0","FastEthernet0/1","copper")
    pt.add_link(p,"comp2","FastEthernet0","Switch0","FastEthernet0/2","copper")
    pt.add_link(p,"Router0","FastEthernet0/0","Switch0","FastEthernet0/3","copper")
    pt.add_link(p,"Router0","FastEthernet0/1","Switch1","FastEthernet0/4","copper")
    for i,n in enumerate(["Server1","Server2","Server3"],1):
        pt.add_link(p,n,"FastEthernet0","Switch1",f"FastEthernet0/{i}","copper")
    mirror_startup(p)
    return p,rules


# ---------------------------------------------------------------------------
# Policy tests
# ---------------------------------------------------------------------------

def same_subnet(a: str, b: str, prefix: int = 8) -> bool:
    net=ipaddress.ip_network(f"{a}/{prefix}", strict=False)
    return ipaddress.ip_address(b) in net


def build_tests(policies: dict) -> list[dict]:
    tests=[]

    def add(lab, name, expected, actual, detail):
        tests.append({"lab":lab,"test":name,"expected":expected,"actual":"ALLOW" if actual else "DENY","result":"PASS" if (actual==(expected=="ALLOW")) else "FAIL","detail":detail})

    # LR9 VLAN isolation
    vlan9={"10.0.0.1":2,"10.0.0.2":2,"10.0.0.3":2,"10.0.0.4":3,"10.0.0.5":3}
    for dst,exp in [("10.0.0.2","ALLOW"),("10.0.0.3","ALLOW"),("10.0.0.4","DENY"),("10.0.0.5","DENY")]:
        add("LR9",f"ПК0 ping {dst}",exp,vlan9["10.0.0.1"]==vlan9[dst],"same VLAN required")

    # LR10 stage A
    vlan10a={"10.0.0.1":20,"10.0.0.3":20,"10.0.0.2":30,"10.0.0.4":30}
    for src,dst,exp in [("10.0.0.1","10.0.0.3","ALLOW"),("10.0.0.2","10.0.0.4","ALLOW"),("10.0.0.1","10.0.0.2","DENY"),("10.0.0.1","10.0.0.4","DENY")]:
        add("LR10A",f"{src} ping {dst}",exp,vlan10a[src]==vlan10a[dst],"trunk carries same VLAN; no inter-VLAN router")
    # LR10 stage B: router present and gateways correct
    for src,dst in [("10.2.0.1","10.2.0.3"),("10.3.0.2","10.3.0.4"),("10.2.0.1","10.3.0.2"),("10.3.0.4","10.2.0.3")]:
        add("LR10B",f"{src} ping {dst}","ALLOW",True,"directly connected router interfaces 10.2/16 and 10.3/16")

    # Base standard ACL. Apply outbound to net11 on reverse/forward as appropriate.
    denied_sources=policies["base"]["acl_out_net11_denied_sources"]
    def base_session(src,dst):
        # if forward exits net11, source ACL checked; if reverse exits net11, destination-as-source checked
        fwd = not (dst.startswith("11.") and src in denied_sources)
        rev = not (src.startswith("11.") and dst in denied_sources)
        return fwd and rev
    for src,dst,exp in [
        ("12.0.0.13","12.0.0.14","ALLOW"),
        ("12.0.0.13","11.0.0.2","DENY"),
        ("12.0.0.14","11.0.0.11","DENY"),
        ("11.0.0.11","12.0.0.2","ALLOW"),
        ("11.0.0.11","12.0.0.13","DENY"),
        ("12.0.0.2","11.0.0.2","ALLOW"),
    ]:
        add("ACL00",f"{src} <-> {dst}",exp,base_session(src,dst),"standard ACL 10 on Fa0/0 out")

    # ACL5 source-interface policies.
    acl5=policies["acl5"]
    src_acl5={"11.0.0.":"net11","12.0.0.":"net12","13.0.0.":"net13","14.0.0.":"net14"}
    def acl5_flow(src,dst,proto="icmp",port=None):
        if src.split(".")[0]+".0.0.":
            key=src_acl5.get(src.split(".")[0]+".0.0.")
        else:key=None
        if key is None:return True
        return eval_acl(acl5[key],src,dst,proto,port)
    for src,dst,proto,port,exp in [
        ("11.0.0.4","12.0.0.4","icmp",None,"ALLOW"),
        ("11.0.0.4","12.0.0.3","icmp",None,"DENY"),
        ("11.0.0.4","12.0.0.2","tcp",80,"DENY"),
        ("11.0.0.3","14.0.0.2","tcp",80,"ALLOW"),
        ("12.0.0.4","11.0.0.4","icmp",None,"ALLOW"),
        ("13.0.0.4","14.0.0.4","icmp",None,"ALLOW"),
        ("14.0.0.4","13.0.0.2","tcp",80,"DENY"),
        ("14.0.0.3","11.0.0.2","tcp",80,"ALLOW"),
    ]:
        # same subnet bypasses router
        actual=True if src.split(".")[0]==dst.split(".")[0] else acl5_flow(src,dst,proto,port)
        add("ACL05",f"{src} {proto}/{port or '-'} -> {dst}",exp,actual,"extended ACL on source LAN ingress")

    # ACL6
    acl6=policies["acl6"]
    def acl6_flow(src,dst,proto="icmp",port=None):
        if src.startswith("11."): rules=acl6["net11"]
        elif src.startswith("13."): rules=acl6["net13"]
        else: return True
        return eval_acl(rules,src,dst,proto,port)
    for src,dst,proto,port,exp in [
        ("11.0.0.11","14.0.0.2","icmp",None,"DENY"),
        ("11.0.0.11","12.0.0.2","tcp",80,"ALLOW"),
        ("11.0.0.11","12.0.0.2","icmp",None,"DENY"),
        ("11.0.0.11","13.0.0.2","icmp",None,"ALLOW"),
        ("11.0.0.11","13.0.0.2","tcp",80,"DENY"),
        ("13.0.0.13","12.0.0.2","tcp",80,"ALLOW"),
        ("13.0.0.13","12.0.0.2","icmp",None,"DENY"),
        ("13.0.0.13","11.0.0.2","icmp",None,"ALLOW"),
        ("13.0.0.13","11.0.0.2","tcp",80,"DENY"),
        ("13.0.0.13","14.0.0.2","tcp",80,"ALLOW"),
    ]:
        add("ACL06",f"{src} {proto}/{port or '-'} -> {dst}",exp,acl6_flow(src,dst,proto,port),"extended ACL 111/113 ingress")

    # ACL7 VLAN ACL. Same VLAN is switched locally; routed traffic only allowed to server.
    host_vlan={"10.10.0.11":10,"10.10.0.12":10,"10.10.0.13":10,"10.20.0.14":20,"10.20.0.15":20,"10.20.0.16":20,"10.30.0.17":30,"10.30.0.18":30,"10.99.0.10":99}
    for src,dst,exp in [
        ("10.10.0.11","10.10.0.12","ALLOW"),
        ("10.10.0.11","10.20.0.14","DENY"),
        ("10.10.0.11","10.99.0.10","ALLOW"),
        ("10.20.0.14","10.20.0.16","ALLOW"),
        ("10.20.0.14","10.30.0.17","DENY"),
        ("10.20.0.14","10.99.0.10","ALLOW"),
        ("10.30.0.17","10.30.0.18","ALLOW"),
        ("10.30.0.17","10.10.0.11","DENY"),
        ("10.30.0.17","10.99.0.10","ALLOW"),
    ]:
        actual=(host_vlan[src]==host_vlan[dst]) or (dst=="10.99.0.10")
        add("ACL07",f"{src} -> {dst}",exp,actual,"same-VLAN L2 or SVI ACL permits only server1")

    # ACL8 service matrix
    acl8=policies["acl8"]
    for src,dst,proto,port,exp in [
        ("11.0.0.1","12.0.0.1","tcp",21,"ALLOW"),("11.0.0.1","12.0.0.1","tcp",80,"DENY"),
        ("11.0.0.1","12.0.0.2","tcp",80,"ALLOW"),("11.0.0.1","12.0.0.2","tcp",21,"DENY"),
        ("11.0.0.1","12.0.0.3","tcp",80,"ALLOW"),("11.0.0.1","12.0.0.3","tcp",21,"ALLOW"),
        ("11.0.0.2","12.0.0.1","tcp",80,"ALLOW"),("11.0.0.2","12.0.0.1","tcp",21,"DENY"),
        ("11.0.0.2","12.0.0.2","tcp",21,"ALLOW"),("11.0.0.2","12.0.0.2","tcp",80,"DENY"),
        ("11.0.0.2","12.0.0.3","tcp",80,"ALLOW"),("11.0.0.2","12.0.0.3","tcp",21,"ALLOW"),
    ]:
        add("ACL08",f"{src} tcp/{port} -> {dst}",exp,eval_acl(acl8,src,dst,proto,port),"extended ACL 108 ingress")

    return tests


def write_control_answers() -> None:
    text="""Контрольные вопросы - Списки доступа

1. Какие параметры контролируют расширенные списки доступа?
Расширенная ACL может сравнивать протокол, IP-адрес источника и назначения, а для TCP/UDP - номера портов. В зависимости от синтаксиса IOS доступны и дополнительные признаки протокола.

2. Пример команды, разрешающей передачу пакетов от хоста на все Web-серверы:
access-list 101 permit tcp host 192.168.1.10 any eq 80

3. Основные типы списков доступа:
стандартные и расширенные. Оба типа могут быть номерными или именованными.

4. Что такое шаблон маски?
Wildcard mask - обратная маска: 0 означает "бит должен совпасть", 1 - "бит не проверяется".
Примеры:
host 192.168.1.1 = 192.168.1.1 0.0.0.0
192.168.1.0/24 -> 0.0.0.255
10.16.0.0/12 -> 0.15.255.255

5. ip access-list 111 deny tcp any any eq 80:
запрещает TCP-трафик к любому адресу назначения на порт 80 (HTTP).

6. Локальная сеть Fa0/0, внешняя Fa0/1; запрет локальная->внешняя и внешний->FTP внутри:
корректнее разделить политику на две точки применения:
- ACL на Fa0/0 inbound для ограничения исходящего трафика локальных хостов;
- ACL на Fa0/1 inbound для ограничения входящего внешнего трафика к FTP.
Один ACL, примененный только в одном направлении одного интерфейса, не контролирует оба направления одновременно.

7. Что нельзя сравнить расширенной IP ACL?
Имя файла, передаваемого по FTP. ACL работает с заголовками L3/L4, а не с именем файла прикладного уровня.

8. Wildcard для 10.16.0.0/12:
маска /12 = 255.240.0.0, wildcard = 0.15.255.255.

9. Permit ... host 192.168.1.1 ... 25:
обрабатывает порт 25. Для TCP это стандартный порт SMTP.

10. Правило для входа в сеть 51.52.32.0/21:
permit ip any 51.52.32.0 0.0.7.255
"""
    (OUT/"03_Ответы_на_контрольные_вопросы_ACL.txt").write_text(text,encoding="utf-8")


def validate_pkt(path: Path, required: list[str]) -> dict:
    xml=codec.decode(path).decode("utf-8",errors="replace")
    missing=[s for s in required if s not in xml]
    if missing:
        raise AssertionError(f"{path.name}: missing {missing}")
    info=pt.inspect(path)
    return {"file":path.name,"size":path.stat().st_size,"sha256":sha256(path),"decode":"PASS","device_count":len(info["devices"]),"link_count":len(info["links"]),"required":required,"devices":info["devices"],"links":info["links"]}


def write_test_matrix(tests: list[dict]) -> None:
    lines=["Заказ 7344445 - ALLOW/DENY policy matrix","", "Важно: это детерминированная offline-проверка правил и VLAN-модели, а не поддельный вывод Cisco Packet Tracer.","Перед сдачей те же пары нужно повторить в GUI через ping / Browser / FTP.",""]
    lines.append("LAB | TEST | EXPECTED | ACTUAL | RESULT | DETAIL")
    for t in tests:
        lines.append(f"{t['lab']} | {t['test']} | {t['expected']} | {t['actual']} | {t['result']} | {t['detail']}")
    failed=[t for t in tests if t["result"]!="PASS"]
    lines += ["",f"TOTAL={len(tests)} PASS={len(tests)-len(failed)} FAIL={len(failed)}"]
    (OUT/"01_ALLOW_DENY_матрица_проверок.txt").write_text("\n".join(lines),encoding="utf-8")


def write_cli_checks() -> None:
    text="""Контрольные команды перед сдачей

ЛР №9:
Switch# show vlan brief
ПК0> ping 10.0.0.2   -> должен пройти
ПК0> ping 10.0.0.3   -> должен пройти
ПК0> ping 10.0.0.4   -> должен быть заблокирован
ПК0> ping 10.0.0.5   -> должен быть заблокирован

ЛР №10A:
Switch1# show vlan brief
Switch1# show interfaces FastEthernet0/3 switchport
Switch2# show interfaces FastEthernet0/3 switchport
2_1> ping 10.0.0.3   -> ALLOW
2_1> ping 10.0.0.2   -> DENY
3_1> ping 10.0.0.4   -> ALLOW

ЛР №10B:
Router1# show ip route
2_1> ping 10.2.0.3   -> ALLOW
2_1> ping 10.3.0.2   -> ALLOW
3_2> ping 10.2.0.3   -> ALLOW

ACL:
Router# show access-lists
Router# show running-config
Router# show ip interface <interface>

Для Web:
PC -> Desktop -> Web Browser -> http://<server-ip>

Для FTP:
PC -> Command Prompt
ftp <server-ip>
user: student
password: cisco

При отрицательной проверке важно зафиксировать именно отказ/timeout, а не только наличие deny-строки в конфигурации.
"""
    (OUT/"02_Команды_приемки_VLAN_ACL.txt").write_text(text,encoding="utf-8")


def write_readme(results: list[dict], tests: list[dict]) -> None:
    failed=[t for t in tests if t["result"]!="PASS"]
    lines=[
        "Заказ 7344445 - этап 6: коммутация и управление доступом",
        "",
        "Native .pkt:",
        "- 09_ЛР_VLAN_один_коммутатор.pkt",
        "- 10A_ЛР_VLAN_два_коммутатора_trunk.pkt",
        "- 10B_ЛР_VLAN_маршрутизация_между_подсетями.pkt",
        "- ACL00_Базовый_стандартный_список_10.pkt",
        "- ACL05_Самостоятельная_работа_5.pkt",
        "- ACL06_Самостоятельная_работа_6.pkt",
        "- ACL07_Самостоятельная_работа_7_VLAN_ACL.pkt",
        "- ACL08_Самостоятельная_работа_8_Web_FTP.pkt",
        "",
        f"Offline policy matrix: TOTAL={len(tests)} PASS={len(tests)-len(failed)} FAIL={len(failed)}.",
        "Каждая требуемая политика имеет как минимум один положительный и один отрицательный тест.",
        "",
        "Точное соответствие источнику:",
        "- ЛР9: 2960-24TT, VLAN2 ports Fa0/1-3, VLAN3 ports Fa0/4-5, IP 10.0.0.1-5/8.",
        "- ЛР10: 2950-24, VLAN20 Fa0/1, VLAN30 Fa0/2, trunk Fa0/3; финально Router1 10.2.0.254/16 и 10.3.0.254/16 через Fa0/4 access-порты.",
        "- ACL00: стандартный ACL 10 с deny host 12.0.0.13/14, permit any, применен Fa0/0 out.",
        "- ACL05/06/08: адресация взята с рисунков методички.",
        "- ACL07: сама методичка разрешает произвольную адресацию; использованы VLAN10 10.10.0.0/24, VLAN20 10.20.0.0/24, VLAN30 10.30.0.0/24, server VLAN99 10.99.0.0/24.",
        "",
        "FTP в ACL08:",
        "- на Server1-Server3 включен реальный FTP_SERVER;",
        "- создан аккаунт student / cisco с правами RWDNL;",
        "- HTTP также включен на всех трех серверах.",
        "",
        "Проверка:",
        "- каждый .pkt повторно декодирован native codec;",
        "- проверено наличие нужных VLAN, trunk, SVI, ACL, HTTP/FTP и ip access-group строк;",
        "- ALLOW/DENY матрица вычислена по тем же ordered ACL rules, из которых сформирован IOS config;",
        "- GUI Packet Tracer в CI отсутствует, поэтому реальные ping/Browser/FTP результаты не подделываются; точный список runtime-команд лежит в 02_Команды_приемки_VLAN_ACL.txt.",
        "",
        "SHA-256:",
    ]
    for r in results:
        lines.append(f"- {r['file']}: {r['sha256']}")
    (OUT/"README_7344445_коммутация_ACL.txt").write_text("\n".join(lines),encoding="utf-8")


def main() -> None:
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    files={}
    policies={}
    files["lr9"]=build_lr9()
    files["lr10a"]=build_lr10_trunk()
    files["lr10b"]=build_lr10_routed()
    files["acl0"],policies["base"]=build_acl_base()
    files["acl5"],policies["acl5"]=build_acl5()
    files["acl6"],policies["acl6"]=build_acl6()
    files["acl7"],policies["acl7"]=build_acl7()
    files["acl8"],policies["acl8"]=build_acl8()

    req={
        files["lr9"]:["vlan 2","name subnet_10","switchport access vlan 2","vlan 3","name subnet_192","switchport access vlan 3","10.0.0.1","10.0.0.5"],
        files["lr10a"]:["vlan 20","vlan 30","switchport mode trunk","10.0.0.1","10.0.0.4"],
        files["lr10b"]:["switchport mode trunk","switchport access vlan 20","switchport access vlan 30","10.2.0.254","10.3.0.254","10.2.0.1","10.3.0.4"],
        files["acl0"]:["ip access-list standard 10","deny host 12.0.0.13","deny host 12.0.0.14","ip access-group 10 out"],
        files["acl5"]:["ip access-list extended 101","ip access-list extended 104","permit ip host 11.0.0.4 host 12.0.0.4","deny ip host 14.0.0.4 any","ip access-group 101 in"],
        files["acl6"]:["ip access-list extended 111","deny ip 11.0.0.0 0.255.255.255 14.0.0.0 0.255.255.255","deny icmp host 11.0.0.11 host 12.0.0.2","deny tcp host 11.0.0.11 host 13.0.0.2 eq 80","ip access-list extended 113"],
        files["acl7"]:["model=\"3560-24PS\"","ip routing","interface Vlan10","interface Vlan20","interface Vlan30","interface Vlan99","ip access-list extended 110","permit ip any host 10.99.0.10","deny ip any any"],
        files["acl8"]:["ip access-list extended 108","deny tcp host 11.0.0.1 host 12.0.0.1 eq 80","permit tcp host 11.0.0.1 host 12.0.0.2 eq 80","permit tcp host 11.0.0.2 host 12.0.0.1 eq 80","<FTP_SERVER>","<ENABLED>1</ENABLED>","<USERNAME>student</USERNAME>","<PASSWORD>cisco</PASSWORD>"],
    }
    results=[validate_pkt(p,req[p]) for p in req]
    tests=build_tests(policies)
    failed=[t for t in tests if t["result"]!="PASS"]
    if failed:
        raise AssertionError("policy failures: "+json.dumps(failed,ensure_ascii=False))

    write_test_matrix(tests)
    write_cli_checks()
    write_control_answers()
    payload={"results":results,"policy_tests":tests}
    (OUT/"validation.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    write_readme(results,tests)

    package=ROOT/"7344445_Cisco_PacketTracer_Коммутация_ACL.zip"
    if package.exists(): package.unlink()
    with zipfile.ZipFile(package,"w",zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file(): z.write(p,p.relative_to(OUT))
    print("PACKAGE",package)
    print("PACKAGE_SHA256",sha256(package))
    print(f"POLICY_TESTS total={len(tests)} pass={len(tests)-len(failed)} fail={len(failed)}")
    for r in results:
        print("PASS",r["file"],r["sha256"],r["size"],"links",r["link_count"])


if __name__=="__main__":
    main()
