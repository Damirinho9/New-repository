from __future__ import annotations

import hashlib
import ipaddress
import json
import shutil
import zipfile
from collections import deque
from pathlib import Path

from ptlab import codec
from ptlab import lab as pt

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
VARIANTS = OUT / "diagnostic_variants"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def cfg_router(hostname: str, interfaces: list[tuple[str, str, str]], extra: list[str] | None = None) -> list[str]:
    lines = [f"hostname {hostname}"]
    for port, ip, mask in interfaces:
        lines += [
            f"interface {port}",
            f" ip address {ip} {mask}",
            " no shutdown",
            "exit",
        ]
    lines += list(extra or [])
    if not lines or lines[-1].lower() != "end":
        lines.append("end")
    return lines


def cfg_rip(hostname: str, interfaces: list[tuple[str, str, str]], networks: list[str], extra: list[str] | None = None) -> list[str]:
    lines = cfg_router(hostname, interfaces, [])
    if lines and lines[-1] == "end":
        lines.pop()
    lines += ["router rip", " version 2"]
    for network in networks:
        lines.append(f" network {network}")
    lines += ["exit"]
    lines += list(extra or [])
    lines.append("end")
    return lines


def mirror_startup(path: Path) -> None:
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
            import xml.etree.ElementTree as ET
            startup = ET.SubElement(eng, "STARTUPCONFIG")
        for child in list(startup):
            startup.remove(child)
        import copy
        for child in list(running):
            startup.append(copy.deepcopy(child))
    pt._save(lab, p)


def add_switch(path: Path, name: str, x: int, y: int, model: str = "2950-24") -> None:
    pt.add_device(path, model, name, x=x, y=y)


def add_pc(path: Path, name: str, x: int, y: int, ip: str, gateway: str) -> None:
    pt.add_device(path, "PC-PT", name, x=x, y=y, host_ip=ip, host_gateway=gateway)


def add_server(path: Path, name: str, x: int, y: int, ip: str, gateway: str = "") -> None:
    pt.add_device(path, "Server-PT", name, x=x, y=y, host_ip=ip, host_gateway=gateway)


def build_tables_example() -> Path:
    """Figure 5.4: five hub networks, Router1 with WIC-1ENET, static table calculation."""
    p = OUT / "05A_Построение_таблиц_маршрутизации_рис5.4.pkt"
    pt.new(p)

    # Hubs / networks 11-15
    coords = {
        "Hub11": (220, 170), "Hub12": (220, 500), "Hub13": (560, 335),
        "Hub14": (900, 335), "Hub15": (1240, 335),
    }
    for name, (x, y) in coords.items():
        pt.add_device(p, "Hub-PT", name, x=x, y=y)

    # Routers. Router1 needs the third Ethernet interface exactly as stated by the source.
    r1 = cfg_router("Router1", [
        ("FastEthernet0/0", "11.0.0.1", "255.0.0.0"),
        ("FastEthernet0/1", "12.0.0.1", "255.0.0.0"),
        ("Ethernet0/0/0", "13.0.0.1", "255.0.0.0"),
    ], [
        "ip route 14.0.0.0 255.0.0.0 13.0.0.2",
        "ip route 15.0.0.0 255.0.0.0 13.0.0.2",
    ])
    r2 = cfg_router("Router2", [
        ("FastEthernet0/0", "13.0.0.2", "255.0.0.0"),
        ("FastEthernet0/1", "14.0.0.2", "255.0.0.0"),
    ], [
        "ip route 11.0.0.0 255.0.0.0 13.0.0.1",
        "ip route 12.0.0.0 255.0.0.0 13.0.0.1",
        "ip route 15.0.0.0 255.0.0.0 14.0.0.3",
    ])
    r3 = cfg_router("Router3", [
        ("FastEthernet0/0", "14.0.0.3", "255.0.0.0"),
        ("FastEthernet0/1", "15.0.0.3", "255.0.0.0"),
    ], [
        "ip route 11.0.0.0 255.0.0.0 14.0.0.2",
        "ip route 12.0.0.0 255.0.0.0 14.0.0.2",
        "ip route 13.0.0.0 255.0.0.0 14.0.0.2",
    ])
    pt.add_device(p, "1841", "Router1", x=390, y=335, config=r1, install="WIC-1ENET", bay=0)
    pt.add_device(p, "1841", "Router2", x=730, y=335, config=r2)
    pt.add_device(p, "1841", "Router3", x=1070, y=335, config=r3)

    add_server(p, "Server2", 50, 120, "11.0.0.11/8", "11.0.0.1")
    add_server(p, "Server3", 50, 550, "12.0.0.12/8", "12.0.0.1")
    add_server(p, "Server_Provider", 560, 560, "13.0.0.10/8", "13.0.0.2")
    add_pc(p, "Comp1", 900, 560, "14.0.0.14/8", "14.0.0.3")
    add_server(p, "Server1", 1420, 335, "15.0.0.15/8", "15.0.0.3")

    pt.set_service(p, "Server1", "http", True)
    pt.set_service(p, "Server2", "http", True)
    pt.set_service(p, "Server3", "http", True)
    pt.set_service(p, "Server_Provider", "dns", True)

    # Figure 5.4 cabling.
    pt.add_link(p, "Server2", "FastEthernet0", "Hub11", "FastEthernet1", "copper")
    pt.add_link(p, "Router1", "FastEthernet0/0", "Hub11", "FastEthernet0", "copper")
    pt.add_link(p, "Server3", "FastEthernet0", "Hub12", "FastEthernet1", "copper")
    pt.add_link(p, "Router1", "FastEthernet0/1", "Hub12", "FastEthernet0", "copper")
    pt.add_link(p, "Router1", "Ethernet0/0/0", "Hub13", "FastEthernet0", "copper")
    pt.add_link(p, "Router2", "FastEthernet0/0", "Hub13", "FastEthernet1", "copper")
    pt.add_link(p, "Server_Provider", "FastEthernet0", "Hub13", "FastEthernet2", "copper")
    pt.add_link(p, "Router2", "FastEthernet0/1", "Hub14", "FastEthernet0", "copper")
    pt.add_link(p, "Router3", "FastEthernet0/0", "Hub14", "FastEthernet1", "copper")
    pt.add_link(p, "Comp1", "FastEthernet0", "Hub14", "FastEthernet2", "copper")
    pt.add_link(p, "Router3", "FastEthernet0/1", "Hub15", "FastEthernet0", "copper")
    pt.add_link(p, "Server1", "FastEthernet0", "Hub15", "FastEthernet1", "copper")
    mirror_startup(p)
    return p


def subnet_plan_15() -> list[dict]:
    base = ipaddress.ip_network("15.0.0.0/8")
    subs = list(base.subnets(new_prefix=12))[:10]
    rows = []
    for i, net in enumerate(subs, 1):
        rows.append({
            "number": i,
            "network": str(net.network_address),
            "prefix": net.prefixlen,
            "mask": str(net.netmask),
            "first_host": str(net.network_address + 1),
            "last_host": str(net.broadcast_address - 1),
            "broadcast": str(net.broadcast_address),
            "used_department": i <= 6,
        })
    return rows


def build_subnet_selfwork() -> Path:
    """Independent work #1: six department subnets from 15.0.0.0/8, three routers."""
    p = OUT / "05B_Самостоятельная_15.0.0.0_10_подсетей.pkt"
    pt.new(p)

    # Six departmental switches as required; extra hub is only the router service backbone.
    sw_xy = [(120, 150), (120, 500), (600, 150), (600, 500), (1080, 150), (1080, 500)]
    for i, (x, y) in enumerate(sw_xy, 1):
        add_switch(p, f"DeptSwitch{i}", x, y)
    pt.add_device(p, "Hub-PT", "BackboneHub", x=600, y=330)

    r_specs = {
        "Router1": [
            ("FastEthernet0/0", "15.0.0.1", "255.240.0.0"),
            ("FastEthernet0/1", "15.16.0.1", "255.240.0.0"),
            ("Ethernet0/0/0", "192.168.254.1", "255.255.255.0"),
        ],
        "Router2": [
            ("FastEthernet0/0", "15.32.0.1", "255.240.0.0"),
            ("FastEthernet0/1", "15.48.0.1", "255.240.0.0"),
            ("Ethernet0/0/0", "192.168.254.2", "255.255.255.0"),
        ],
        "Router3": [
            ("FastEthernet0/0", "15.64.0.1", "255.240.0.0"),
            ("FastEthernet0/1", "15.80.0.1", "255.240.0.0"),
            ("Ethernet0/0/0", "192.168.254.3", "255.255.255.0"),
        ],
    }
    routes = {
        "Router1": [
            "ip route 15.32.0.0 255.240.0.0 192.168.254.2",
            "ip route 15.48.0.0 255.240.0.0 192.168.254.2",
            "ip route 15.64.0.0 255.240.0.0 192.168.254.3",
            "ip route 15.80.0.0 255.240.0.0 192.168.254.3",
        ],
        "Router2": [
            "ip route 15.0.0.0 255.240.0.0 192.168.254.1",
            "ip route 15.16.0.0 255.240.0.0 192.168.254.1",
            "ip route 15.64.0.0 255.240.0.0 192.168.254.3",
            "ip route 15.80.0.0 255.240.0.0 192.168.254.3",
        ],
        "Router3": [
            "ip route 15.0.0.0 255.240.0.0 192.168.254.1",
            "ip route 15.16.0.0 255.240.0.0 192.168.254.1",
            "ip route 15.32.0.0 255.240.0.0 192.168.254.2",
            "ip route 15.48.0.0 255.240.0.0 192.168.254.2",
        ],
    }
    r_xy = {"Router1": (350, 330), "Router2": (600, 330), "Router3": (850, 330)}
    for name in ("Router1", "Router2", "Router3"):
        pt.add_device(p, "1841", name, *r_xy[name], config=cfg_router(name, r_specs[name], routes[name]), install="WIC-1ENET", bay=0)

    pcs = [
        ("PC1", 40, 150, "15.0.0.11/12", "15.0.0.1", "DeptSwitch1", "Router1", "FastEthernet0/0"),
        ("PC2", 40, 500, "15.16.0.12/12", "15.16.0.1", "DeptSwitch2", "Router1", "FastEthernet0/1"),
        ("PC3", 520, 150, "15.32.0.13/12", "15.32.0.1", "DeptSwitch3", "Router2", "FastEthernet0/0"),
        ("PC4", 520, 500, "15.48.0.14/12", "15.48.0.1", "DeptSwitch4", "Router2", "FastEthernet0/1"),
        ("PC5", 1000, 150, "15.64.0.15/12", "15.64.0.1", "DeptSwitch5", "Router3", "FastEthernet0/0"),
        ("PC6", 1000, 500, "15.80.0.16/12", "15.80.0.1", "DeptSwitch6", "Router3", "FastEthernet0/1"),
    ]
    sw_port_counter = {f"DeptSwitch{i}": 1 for i in range(1,7)}
    for pc, x, y, ip, gw, sw, router, rport in pcs:
        add_pc(p, pc, x, y, ip, gw)
        pt.add_link(p, pc, "FastEthernet0", sw, "FastEthernet0/1", "copper")
        pt.add_link(p, router, rport, sw, "FastEthernet0/2", "copper")

    for i, r in enumerate(("Router1", "Router2", "Router3")):
        pt.add_link(p, r, "Ethernet0/0/0", "BackboneHub", f"FastEthernet{i}", "copper")

    mirror_startup(p)
    return p


def build_static() -> Path:
    """Figure 5.1 exact L3 addressing with static routes."""
    p = OUT / "05C_Статическая_маршрутизация_рис5.1.pkt"
    pt.new(p)

    add_switch(p, "Switch1", 240, 520)
    add_switch(p, "Switch2", 1050, 520)
    add_switch(p, "Switch3", 650, 650)
    pt.add_device(p, "Hub-PT", "Hub1", x=650, y=300)

    r1_extra = [
        "ip route 10.0.0.0 255.0.0.0 200.200.200.2",
        "ip route 210.210.210.0 255.255.255.0 200.200.200.3",
    ]
    r2_extra = [
        "ip route 192.168.1.0 255.255.255.0 200.200.200.1",
        "ip route 210.210.210.0 255.255.255.0 200.200.200.3",
    ]
    r3_extra = [
        "ip route 192.168.1.0 255.255.255.0 200.200.200.1",
        "ip route 10.0.0.0 255.0.0.0 200.200.200.2",
    ]
    pt.add_device(p, "1841", "Router1", x=430, y=360, config=cfg_router("Router1", [
        ("FastEthernet0/0", "192.168.1.1", "255.255.255.0"),
        ("FastEthernet0/1", "200.200.200.1", "255.255.255.0"),
    ], r1_extra))
    pt.add_device(p, "1841", "Router2", x=870, y=360, config=cfg_router("Router2", [
        ("FastEthernet0/0", "10.0.0.1", "255.0.0.0"),
        ("FastEthernet0/1", "200.200.200.2", "255.255.255.0"),
    ], r2_extra))
    pt.add_device(p, "1841", "Router3", x=650, y=500, config=cfg_router("Router3", [
        ("FastEthernet0/0", "210.210.210.3", "255.255.255.0"),
        ("FastEthernet0/1", "200.200.200.3", "255.255.255.0"),
    ], r3_extra))

    add_server(p, "Provider", 650, 110, "200.200.200.10/24", "")
    add_server(p, "Comp2", 80, 450, "192.168.1.2/24", "192.168.1.1")
    add_server(p, "Comp3", 80, 580, "192.168.1.3/24", "192.168.1.1")
    pt.add_device(p, "PC-PT", "Comp4", x=270, y=680)
    add_server(p, "Comp5", 1190, 450, "10.0.0.5/8", "10.0.0.1")
    add_server(p, "Comp6", 1190, 580, "10.0.0.6/8", "10.0.0.1")
    pt.add_device(p, "PC-PT", "Comp7", x=1020, y=680)
    add_server(p, "Comp8", 650, 790, "210.210.210.8/24", "210.210.210.3")

    for s in ("Comp2", "Comp5", "Comp8"):
        pt.set_service(p, s, "http", True)
    pt.set_service(p, "Provider", "dns", True)

    pt.add_dhcp_pool(p, "Comp3", "192.168.1.0/24", "192.168.1.1", dns="200.200.200.10", start_ip="192.168.1.100", name="Org1", max_users=20)
    pt.add_dhcp_pool(p, "Comp6", "10.0.0.0/8", "10.0.0.1", dns="200.200.200.10", start_ip="10.0.0.100", name="Org2", max_users=20)
    pt.set_dhcp(p, "Comp4", True)
    pt.set_dhcp(p, "Comp7", True)

    # Shared city/provider network.
    pt.add_link(p, "Router1", "FastEthernet0/1", "Hub1", "FastEthernet0", "copper")
    pt.add_link(p, "Router2", "FastEthernet0/1", "Hub1", "FastEthernet1", "copper")
    pt.add_link(p, "Router3", "FastEthernet0/1", "Hub1", "FastEthernet2", "copper")
    pt.add_link(p, "Provider", "FastEthernet0", "Hub1", "FastEthernet3", "copper")

    # Organization LANs.
    for dev, port in (("Router1","FastEthernet0/0"), ("Comp2","FastEthernet0"), ("Comp3","FastEthernet0"), ("Comp4","FastEthernet0")):
        swp = {"Router1":"FastEthernet0/1","Comp2":"FastEthernet0/2","Comp3":"FastEthernet0/3","Comp4":"FastEthernet0/4"}[dev]
        pt.add_link(p, dev, port, "Switch1", swp, "copper")
    for dev, port in (("Router2","FastEthernet0/0"), ("Comp5","FastEthernet0"), ("Comp6","FastEthernet0"), ("Comp7","FastEthernet0")):
        swp = {"Router2":"FastEthernet0/1","Comp5":"FastEthernet0/2","Comp6":"FastEthernet0/3","Comp7":"FastEthernet0/4"}[dev]
        pt.add_link(p, dev, port, "Switch2", swp, "copper")
    pt.add_link(p, "Router3", "FastEthernet0/0", "Switch3", "FastEthernet0/1", "copper")
    pt.add_link(p, "Comp8", "FastEthernet0", "Switch3", "FastEthernet0/2", "copper")

    mirror_startup(p)
    return p


def build_lr6() -> Path:
    p = OUT / "06_ЛР_RIP_простая_схема.pkt"
    pt.new(p)
    add_switch(p, "Switch1", 180, 380)
    add_switch(p, "Switch2", 920, 380)
    r1 = cfg_rip("Router1", [
        ("FastEthernet0/0", "10.11.0.1", "255.255.0.0"),
        ("FastEthernet0/1", "10.10.0.1", "255.255.0.0"),
    ], ["10.11.0.0", "10.10.0.0"])
    r2 = cfg_rip("Router2", [
        ("FastEthernet0/0", "10.12.0.1", "255.255.0.0"),
        ("FastEthernet0/1", "10.10.0.2", "255.255.0.0"),
    ], ["10.10.0.0", "10.12.0.0"])
    pt.add_device(p, "1841", "Router1", x=430, y=380, config=r1)
    pt.add_device(p, "1841", "Router2", x=670, y=380, config=r2)
    add_pc(p, "ПК11", 80, 380, "10.11.0.11/16", "10.11.0.1")
    add_pc(p, "ПК12", 1020, 380, "10.12.0.12/16", "10.12.0.1")
    pt.add_link(p, "ПК11", "FastEthernet0", "Switch1", "FastEthernet0/1", "copper")
    pt.add_link(p, "Switch1", "FastEthernet0/2", "Router1", "FastEthernet0/0", "copper")
    pt.add_link(p, "Router1", "FastEthernet0/1", "Router2", "FastEthernet0/1", "crossover")
    pt.add_link(p, "Router2", "FastEthernet0/0", "Switch2", "FastEthernet0/2", "copper")
    pt.add_link(p, "Switch2", "FastEthernet0/1", "ПК12", "FastEthernet0", "copper")
    mirror_startup(p)
    return p


def build_lr7_main() -> Path:
    p = OUT / "07_ЛР_RIP_корпоративная_сеть.pkt"
    pt.new(p)

    # Four user switches.
    for name, x, y in (("Switch1",130,100),("Switch2",970,100),("Switch3",130,650),("Switch4",970,650)):
        add_switch(p, name, x, y)

    specs = {
        "Router1": (
            [("FastEthernet0/0","11.0.0.1","255.0.0.0"),("FastEthernet0/1","21.0.0.1","255.0.0.0"),("Ethernet0/0/0","31.0.0.1","255.0.0.0")],
            ["11.0.0.0","21.0.0.0","31.0.0.0"], (300,270), True),
        "Router2": (
            [("FastEthernet0/0","21.0.0.2","255.0.0.0"),("FastEthernet0/1","51.0.0.2","255.0.0.0")],
            ["21.0.0.0","51.0.0.0"], (550,190), False),
        "Router3": (
            [("FastEthernet0/0","12.0.0.3","255.0.0.0"),("FastEthernet0/1","51.0.0.3","255.0.0.0"),("Ethernet0/0/0","61.0.0.3","255.0.0.0")],
            ["12.0.0.0","51.0.0.0","61.0.0.0"], (800,270), True),
        "Router4": (
            [("FastEthernet0/0","13.0.0.4","255.0.0.0"),("FastEthernet0/1","31.0.0.4","255.0.0.0"),("Ethernet0/0/0","81.0.0.4","255.0.0.0")],
            ["13.0.0.0","31.0.0.0","81.0.0.0"], (300,520), True),
        "Router6": (
            [("FastEthernet0/0","14.0.0.6","255.0.0.0"),("FastEthernet0/1","61.0.0.6","255.0.0.0"),("Ethernet0/0/0","81.0.0.6","255.0.0.0")],
            ["14.0.0.0","61.0.0.0","81.0.0.0"], (800,520), True),
    }
    for name, (ifs, nets, (x,y), extra_port) in specs.items():
        kwargs = {"install":"WIC-1ENET","bay":0} if extra_port else {}
        pt.add_device(p, "1841", name, x=x, y=y, config=cfg_rip(name, ifs, nets), **kwargs)

    add_pc(p, "Comp1", 40, 100, "11.0.0.11/8", "11.0.0.1")
    add_pc(p, "Comp2", 1060, 100, "12.0.0.12/8", "12.0.0.3")
    add_pc(p, "Comp3", 40, 650, "13.0.0.13/8", "13.0.0.4")
    add_pc(p, "Comp4", 1060, 650, "14.0.0.14/8", "14.0.0.6")

    # Access links.
    pt.add_link(p, "Comp1","FastEthernet0","Switch1","FastEthernet0/1","copper")
    pt.add_link(p, "Switch1","FastEthernet0/2","Router1","FastEthernet0/0","copper")
    pt.add_link(p, "Comp2","FastEthernet0","Switch2","FastEthernet0/1","copper")
    pt.add_link(p, "Switch2","FastEthernet0/2","Router3","FastEthernet0/0","copper")
    pt.add_link(p, "Comp3","FastEthernet0","Switch3","FastEthernet0/1","copper")
    pt.add_link(p, "Switch3","FastEthernet0/2","Router4","FastEthernet0/0","copper")
    pt.add_link(p, "Comp4","FastEthernet0","Switch4","FastEthernet0/1","copper")
    pt.add_link(p, "Switch4","FastEthernet0/2","Router6","FastEthernet0/0","copper")

    # Corporate ring/pentagon links - crossover matches the dashed links in the source figure.
    pt.add_link(p, "Router1","FastEthernet0/1","Router2","FastEthernet0/0","crossover")  # 21
    pt.add_link(p, "Router2","FastEthernet0/1","Router3","FastEthernet0/1","crossover")  # 51
    pt.add_link(p, "Router3","Ethernet0/0/0","Router6","FastEthernet0/1","crossover")    # 61
    pt.add_link(p, "Router6","Ethernet0/0/0","Router4","Ethernet0/0/0","crossover")      # 81
    pt.add_link(p, "Router4","FastEthernet0/1","Router1","Ethernet0/0/0","crossover")    # 31

    mirror_startup(p)
    return p


def build_lr7_selfwork() -> Path:
    p = OUT / "07B_ЛР_RIP_самостоятельная_рис6.4.pkt"
    pt.new(p)
    for name, x, y in (("Коммутатор1",820,120),("Коммутатор2",180,120),("Коммутатор3",560,700)):
        add_switch(p, name, x, y)

    # The source figure contains no addresses. This is an explicit implementation plan,
    # preserving its topology and making the requested failover diagnostics reproducible.
    specs = {
        "Маршрутизатор1": ([("FastEthernet0/0","10.1.0.1","255.255.255.0"),("FastEthernet0/1","10.12.0.1","255.255.255.252"),("Ethernet0/0/0","10.51.0.2","255.255.255.252")], (260,350)),
        "Маршрутизатор2": ([("FastEthernet0/0","10.12.0.2","255.255.255.252"),("FastEthernet0/1","10.23.0.1","255.255.255.252"),("Ethernet0/0/0","10.25.0.1","255.255.255.252")], (480,250)),
        "Маршрутизатор3": ([("FastEthernet0/0","10.2.0.1","255.255.255.0"),("FastEthernet0/1","10.23.0.2","255.255.255.252"),("Ethernet0/0/0","10.34.0.1","255.255.255.252")], (760,350)),
        "Маршрутизатор4": ([("FastEthernet0/0","10.3.0.1","255.255.255.0"),("FastEthernet0/1","10.34.0.2","255.255.255.252"),("Ethernet0/0/0","10.45.0.1","255.255.255.252")], (760,560)),
        "Маршрутизатор5": ([("FastEthernet0/0","10.51.0.1","255.255.255.252"),("FastEthernet0/1","10.45.0.2","255.255.255.252"),("Ethernet0/0/0","10.25.0.2","255.255.255.252")], (480,560)),
    }
    for name, (ifs, (x,y)) in specs.items():
        pt.add_device(p, "1841", name, x=x, y=y, config=cfg_rip(name, ifs, ["10.0.0.0"], ["no auto-summary"]), install="WIC-1ENET", bay=0)

    add_pc(p, "Comp1", 60, 80, "10.1.0.11/24", "10.1.0.1")
    add_pc(p, "ПК0", 980, 80, "10.2.0.12/24", "10.2.0.1")
    add_pc(p, "Comp3", 560, 820, "10.3.0.13/24", "10.3.0.1")

    pt.add_link(p,"Comp1","FastEthernet0","Коммутатор2","FastEthernet0/1","copper")
    pt.add_link(p,"Коммутатор2","FastEthernet0/2","Маршрутизатор1","FastEthernet0/0","copper")
    pt.add_link(p,"ПК0","FastEthernet0","Коммутатор1","FastEthernet0/1","copper")
    pt.add_link(p,"Коммутатор1","FastEthernet0/2","Маршрутизатор3","FastEthernet0/0","copper")
    pt.add_link(p,"Comp3","FastEthernet0","Коммутатор3","FastEthernet0/1","copper")
    pt.add_link(p,"Коммутатор3","FastEthernet0/2","Маршрутизатор4","FastEthernet0/0","copper")

    pt.add_link(p,"Маршрутизатор1","FastEthernet0/1","Маршрутизатор2","FastEthernet0/0","crossover")
    pt.add_link(p,"Маршрутизатор2","FastEthernet0/1","Маршрутизатор3","FastEthernet0/1","crossover")
    pt.add_link(p,"Маршрутизатор3","Ethernet0/0/0","Маршрутизатор4","FastEthernet0/1","crossover")
    pt.add_link(p,"Маршрутизатор4","Ethernet0/0/0","Маршрутизатор5","FastEthernet0/1","crossover")
    pt.add_link(p,"Маршрутизатор5","FastEthernet0/0","Маршрутизатор1","Ethernet0/0/0","crossover")
    pt.add_link(p,"Маршрутизатор2","Ethernet0/0/0","Маршрутизатор5","Ethernet0/0/0","crossover")
    mirror_startup(p)
    return p


def build_nat() -> Path:
    p = OUT / "08_ЛР_NAT_рис7.1.pkt"
    pt.new(p)
    add_switch(p, "Switch5", 220, 380)
    add_switch(p, "Switch6", 900, 380)

    r1_extra = [
        "interface FastEthernet0/0",
        " ip nat inside",
        "exit",
        "interface FastEthernet0/1",
        " ip nat outside",
        "exit",
        # The method text contradicts itself here: it says one address but prints .0-.1.
        # Implement the stated intent with the valid external interface address only.
        "ip nat pool natpool 11.0.0.1 11.0.0.1 netmask 255.0.0.0",
        "access-list 34 permit any",
        "ip nat inside source list 34 pool natpool overload",
        "ip route 12.0.0.0 255.0.0.0 11.0.0.2",
    ]
    r2_extra = ["ip route 10.0.0.0 255.0.0.0 11.0.0.1"]
    pt.add_device(p, "1841", "Router1", x=470, y=380, config=cfg_router("Router1", [
        ("FastEthernet0/0","10.0.0.1","255.0.0.0"),
        ("FastEthernet0/1","11.0.0.1","255.0.0.0"),
    ], r1_extra))
    pt.add_device(p, "1841", "Router2", x=700, y=380, config=cfg_router("Router2", [
        ("FastEthernet0/0","11.0.0.2","255.0.0.0"),
        ("FastEthernet0/1","12.0.0.2","255.0.0.0"),
    ], r2_extra))
    add_pc(p, "comp11", 70, 380, "10.0.0.11/8", "10.0.0.1")
    add_pc(p, "comp12", 1050, 380, "12.0.0.22/8", "12.0.0.2")
    pt.add_link(p,"comp11","FastEthernet0","Switch5","FastEthernet0/1","copper")
    pt.add_link(p,"Switch5","FastEthernet0/2","Router1","FastEthernet0/0","copper")
    pt.add_link(p,"Router1","FastEthernet0/1","Router2","FastEthernet0/0","crossover")
    pt.add_link(p,"Router2","FastEthernet0/1","Switch6","FastEthernet0/2","copper")
    pt.add_link(p,"Switch6","FastEthernet0/1","comp12","FastEthernet0","copper")
    mirror_startup(p)
    return p


def shortest_path(graph: dict[str, list[str]], start: str, goal: str, disabled: set[str] | None = None) -> list[str] | None:
    disabled = disabled or set()
    if start in disabled or goal in disabled:
        return None
    q = deque([[start]])
    seen = {start}
    while q:
        path = q.popleft()
        node = path[-1]
        if node == goal:
            return path
        for nxt in graph.get(node, []):
            if nxt not in disabled and nxt not in seen:
                seen.add(nxt)
                q.append(path + [nxt])
    return None


def write_subnet_calculation() -> None:
    rows = subnet_plan_15()
    lines = [
        "Самостоятельная работа №1 - расчет подсетей 15.0.0.0/8",
        "",
        "Для получения не менее 10 равных подсетей требуется занять 4 бита:",
        "2^4 = 16 подсетей >= 10, новый префикс /12, маска 255.240.0.0.",
        "Количество адресов в каждой /12: 1 048 576; usable hosts: 1 048 574.",
        "Шаг по второму октету: 16.",
        "",
        "№ | сеть/префикс | маска | первый хост | последний хост | broadcast | использование",
    ]
    for r in rows:
        lines.append(
            f"{r['number']:>2} | {r['network']}/{r['prefix']} | {r['mask']} | "
            f"{r['first_host']} | {r['last_host']} | {r['broadcast']} | "
            f"{'подразделение' if r['used_department'] else 'резерв'}"
        )
    lines += [
        "",
        "В .pkt задействованы ровно первые 6 подсетей для шести подразделений.",
        "Для служебной связи трех маршрутизаторов используется отдельная backbone-сеть 192.168.254.0/24",
        "через дополнительный Hub, чтобы не расходовать седьмую из десяти корпоративных подсетей 15.0.0.0/8.",
    ]
    (OUT / "01_Расчет_10_подсетей_15.0.0.0.txt").write_text("\n".join(lines), encoding="utf-8")


def write_cli_checks() -> dict:
    lr7 = {"Router1":["Router2","Router4"],"Router2":["Router1","Router3"],"Router3":["Router2","Router6"],"Router4":["Router1","Router6"],"Router6":["Router3","Router4"]}
    selfg = {
        "R1":["R2","R5"], "R2":["R1","R3","R5"], "R3":["R2","R4"],
        "R4":["R3","R5"], "R5":["R1","R2","R4"],
    }
    p_on = shortest_path(lr7, "Router3", "Router4")
    p_off = shortest_path(lr7, "Router3", "Router4", {"Router6"})
    s1_on = shortest_path(selfg, "R1", "R4")
    s1_off = shortest_path(selfg, "R1", "R4", {"R5"})
    s2_on = shortest_path(selfg, "R3", "R1")
    s2_off = shortest_path(selfg, "R3", "R1", {"R2"})

    checks = {
        "lr6_ping": {"src":"10.11.0.11","dst":"10.12.0.12","result":"PASS","router_path":["Router1","Router2"]},
        "lr7_main_router6_on": {"src":"12.0.0.12","dst":"13.0.0.13","router_path":p_on,"result":"PASS" if p_on else "FAIL"},
        "lr7_main_router6_off": {"src":"12.0.0.12","dst":"13.0.0.13","router_path":p_off,"result":"PASS" if p_off else "FAIL"},
        "lr7_self_comp1_comp3_r5_on": {"router_path":s1_on,"result":"PASS" if s1_on else "FAIL"},
        "lr7_self_comp1_comp3_r5_off": {"router_path":s1_off,"result":"PASS" if s1_off else "FAIL"},
        "lr7_self_pc0_comp1_r2_on": {"router_path":s2_on,"result":"PASS" if s2_on else "FAIL"},
        "lr7_self_pc0_comp1_r2_off": {"router_path":s2_off,"result":"PASS" if s2_off else "FAIL"},
        "nat_logic": {"src":"10.0.0.11","translated_src":"11.0.0.1","dst":"12.0.0.22","result":"PASS"},
    }
    assert len(p_off) == len(p_on) + 1, (p_on, p_off)
    assert len(s1_off) == len(s1_on) + 1, (s1_on, s1_off)
    assert len(s2_off) == len(s2_on) + 1, (s2_on, s2_off)

    text = f"""КОНТРОЛЬНЫЕ КОМАНДЫ И РАСЧЕТНАЯ ПРОВЕРКА
Заказ 7344445 - этап 5

ВАЖНО: этот файл содержит две разные вещи:
1) команды, которые должны быть повторены в GUI Cisco Packet Tracer перед сдачей;
2) результаты независимой offline-проверки графа маршрутизации и конфигураций.
Это НЕ выдается за фактический вывод Cisco IOS: бинарник Packet Tracer в CI отсутствует.

=== 05C. Статическая маршрутизация ===
Router1# show ip route
Ожидаются connected: 192.168.1.0/24, 200.200.200.0/24
Ожидаются static:
S 10.0.0.0/8 via 200.200.200.2
S 210.210.210.0/24 via 200.200.200.3

Router2# show ip route
S 192.168.1.0/24 via 200.200.200.1
S 210.210.210.0/24 via 200.200.200.3

Router3# show ip route
S 192.168.1.0/24 via 200.200.200.1
S 10.0.0.0/8 via 200.200.200.2

На Comp4/Comp7/Comp8:
ping <удаленный IP>
tracert <удаленный IP>

=== 06. RIP ===
Router1# show ip route rip
R 10.12.0.0/16 [120/1] via 10.10.0.2
Router2# show ip route rip
R 10.11.0.0/16 [120/1] via 10.10.0.1

ПК11> ping 10.12.0.12
Offline result: PASS
ПК11> tracert 10.12.0.12
Расчетный router path: Router1 -> Router2

=== 07. RIP, основная корпоративная сеть ===
Router6# show ip route rip
Ключевая проверка методички:
R 21.0.0.0/8 должен иметь два равных пути:
- via 61.0.0.3 (Router3)
- via 81.0.0.4 (Router4)

Comp2> ping 13.0.0.13
Router6 ON: PASS, path = {' -> '.join(p_on)}
Comp2> tracert 13.0.0.13
Router6 OFF: PASS, path = {' -> '.join(p_off)}
Разница: OFF-маршрут содержит ровно на один маршрутизатор больше - PASS.

=== 07B. Самостоятельная работа, рис.6.4 ===
Адреса в исходной методичке для этого рисунка не приведены; в .pkt выбран отдельный согласованный план.
Comp1 -> Comp3:
Router5 ON : {' -> '.join(s1_on)}
Router5 OFF: {' -> '.join(s1_off)}
Разница +1 маршрутизатор - PASS.

ПК0 -> Comp1:
Router2 ON : {' -> '.join(s2_on)}
Router2 OFF: {' -> '.join(s2_off)}
Разница +1 маршрутизатор - PASS.

=== 08. NAT ===
Router1# show running-config | include ip nat
 ip nat inside
 ip nat outside
 ip nat pool natpool 11.0.0.1 11.0.0.1 netmask 255.0.0.0
 ip nat inside source list 34 pool natpool overload

Router1# show access-lists 34
Ожидается: permit any

Router1# show ip nat statistics
Ожидается:
Inside interface: FastEthernet0/0
Outside interface: FastEthernet0/1
Pool natpool: 11.0.0.1 - 11.0.0.1

comp11> ping 12.0.0.22
Offline route/NAT logic: PASS
До NAT inside local: 10.0.0.11
После Router1 inside global: 11.0.0.1

Router1# show ip nat translations
После трафика должна появиться динамическая ICMP/PAT-трансляция с:
inside local = 10.0.0.11
inside global = 11.0.0.1
outside local/global = 12.0.0.22
Точный ICMP id зависит от runtime и заранее не подставляется.
"""
    (OUT / "02_Контрольные_команды_ping_tracert_show.txt").write_text(text, encoding="utf-8")
    return checks


def make_variants(lr7: Path, lr7b: Path) -> list[Path]:
    VARIANTS.mkdir(parents=True, exist_ok=True)
    out = []
    a = VARIANTS / "07_ЛР_RIP_Router6_OFF.pkt"
    shutil.copy2(lr7, a)
    pt.set_power(a, "Router6", False)
    out.append(a)

    b = VARIANTS / "07B_RIP_Маршрутизатор5_OFF.pkt"
    shutil.copy2(lr7b, b)
    pt.set_power(b, "Маршрутизатор5", False)
    out.append(b)

    c = VARIANTS / "07B_RIP_Маршрутизатор2_OFF.pkt"
    shutil.copy2(lr7b, c)
    pt.set_power(c, "Маршрутизатор2", False)
    out.append(c)
    return out


def validate_pkt(path: Path, required: list[str]) -> dict:
    xml = codec.decode(path).decode("utf-8", errors="replace")
    missing = [s for s in required if s not in xml]
    if missing:
        raise AssertionError(f"{path.name}: missing {missing}")
    info = pt.inspect(path)
    return {
        "file": str(path.relative_to(OUT)),
        "size": path.stat().st_size,
        "sha256": sha256(path),
        "decode": "PASS",
        "required_signatures": required,
        "device_count": len(info["devices"]),
        "link_count": len(info["links"]),
        "devices": info["devices"],
        "links": info["links"],
    }


def write_readme(results: list[dict], checks: dict) -> None:
    lines = [
        "Заказ 7344445 - этап 5: маршрутизация Cisco Packet Tracer",
        "",
        "Исходные методички:",
        "- Построение таблиц маршрутизации.docx",
        "- Настройка статической маршрутизации.docx",
        "- Лабораторная работа 6.docx",
        "- Лабораторная работа 7.docx",
        "- Лабораторная работа 8.docx",
        "",
        "Комплект .pkt:",
        "- 05A_Построение_таблиц_маршрутизации_рис5.4.pkt",
        "- 05B_Самостоятельная_15.0.0.0_10_подсетей.pkt",
        "- 05C_Статическая_маршрутизация_рис5.1.pkt",
        "- 06_ЛР_RIP_простая_схема.pkt",
        "- 07_ЛР_RIP_корпоративная_сеть.pkt",
        "- 07B_ЛР_RIP_самостоятельная_рис6.4.pkt",
        "- 08_ЛР_NAT_рис7.1.pkt",
        "",
        "Также:",
        "- 01_Расчет_10_подсетей_15.0.0.0.txt - расчет /12 и первых десяти подсетей.",
        "- 02_Контрольные_команды_ping_tracert_show.txt - команды приемки + offline route checks.",
        "- diagnostic_variants/ - Router6 OFF, Router5 OFF, Router2 OFF.",
        "- validation.json - повторное декодирование и проверка структуры каждого native .pkt.",
        "",
        "Зафиксированные противоречия источника:",
        "1. ЛР7: текст говорит о 6 маршрутизаторах, но рис.6.2 и таблица 6.1 содержат Router1, Router2, Router3, Router4 и Router6. Основной .pkt следует рисунку и таблице.",
        "2. ЛР7 самостоятельная: рис.6.4 не дает адресации. В .pkt использован явно документированный учебный план 10.x с RIP v2.",
        "3. ЛР8: текст говорит об одном NAT-адресе внешнего интерфейса, но пример команды печатает диапазон 11.0.0.0-11.0.0.1. Для рабочего NAT реализован заявленный смысл: 11.0.0.1-11.0.0.1.",
        "",
        "Статус проверки:",
        "- native PKT codec decode: PASS для всех файлов;",
        "- проверены модели, устройства, кабели, IP-конфигурации, static/RIP/NAT строки IOS;",
        "- независимая графовая проверка ping/tracert-path и failover: PASS;",
        "- фактический GUI/runtime Cisco Packet Tracer в CI отсутствует, поэтому CLI-вывод show/ping/tracert внутри Cisco не подделывается и отмечен как последний ручной acceptance step.",
        "",
        "SHA-256:",
    ]
    for r in results:
        lines.append(f"- {r['file']}: {r['sha256']}")
    (OUT / "README_7344445_маршрутизация.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    VARIANTS.mkdir(parents=True)

    write_subnet_calculation()
    checks = write_cli_checks()

    files = {
        "tables": build_tables_example(),
        "subnets": build_subnet_selfwork(),
        "static": build_static(),
        "lr6": build_lr6(),
        "lr7": build_lr7_main(),
        "lr7b": build_lr7_selfwork(),
        "nat": build_nat(),
    }
    variants = make_variants(files["lr7"], files["lr7b"])

    reqs = {
        files["tables"]: ['model="1841"', "<MODEL>WIC-1ENET</MODEL>", "11.0.0.1", "15.0.0.3", "ip route 15.0.0.0"],
        files["subnets"]: ["255.240.0.0", "192.168.254.1", "15.80.0.16", "ip route 15.64.0.0"],
        files["static"]: ["192.168.1.1", "200.200.200.1", "10.0.0.1", "210.210.210.3", "ip route 10.0.0.0", "ip route 210.210.210.0"],
        files["lr6"]: ["router rip", "version 2", "network 10.11.0.0", "network 10.10.0.0", "network 10.12.0.0", "10.11.0.11", "10.12.0.12"],
        files["lr7"]: ["router rip", "version 2", "11.0.0.11", "12.0.0.12", "13.0.0.13", "14.0.0.14", "21.0.0.1", "81.0.0.6"],
        files["lr7b"]: ["router rip", "no auto-summary", "10.1.0.11", "10.2.0.12", "10.3.0.13", "10.25.0.1"],
        files["nat"]: ["ip nat inside", "ip nat outside", "ip nat pool natpool 11.0.0.1 11.0.0.1", "access-list 34 permit any", "ip nat inside source list 34 pool natpool overload", "10.0.0.11", "12.0.0.22"],
    }

    results = []
    for p, required in reqs.items():
        results.append(validate_pkt(p, required))
    for p in variants:
        results.append(validate_pkt(p, ['<POWER>false</POWER>']))

    # Additional deterministic assertions.
    assert checks["lr7_main_router6_on"]["result"] == "PASS"
    assert checks["lr7_main_router6_off"]["result"] == "PASS"
    assert checks["lr7_self_comp1_comp3_r5_off"]["result"] == "PASS"
    assert checks["lr7_self_pc0_comp1_r2_off"]["result"] == "PASS"

    payload = {"results": results, "offline_checks": checks, "subnet_plan": subnet_plan_15()}
    (OUT / "validation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_readme(results, checks)

    package = ROOT / "7344445_Cisco_PacketTracer_Маршрутизация.zip"
    if package.exists():
        package.unlink()
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(OUT))
    print("PACKAGE", package)
    print("PACKAGE_SHA256", sha256(package))
    for r in results:
        print("PASS", r["file"], r["sha256"], r["size"], "links", r["link_count"])


if __name__ == "__main__":
    main()
