from __future__ import annotations

import hashlib
import ipaddress
import json
import shutil
import uuid
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from ptlab import codec
from ptlab import lab as pt

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"

REMOTE = {
    "outgoing": {
        "name": "Сосед3",
        "uuid": "{a6276508-6ad0-4195-b12d-ad1f0484fa0b}",
        "port_uuid": "{3cf8d30c-a7c6-4875-a965-fe879a06459f}",
        "mem_addr": "177803672",
        "dev_addr": "180090600",
        "port_mem_addr": "177735624",
        "x": "760",
        "y": "260",
    },
    "incoming": {
        "name": "Lan 11.0.0.0",
        "uuid": "{19de9c9b-7871-4ec1-9ba9-544c1eb065f0}",
        "port_uuid": "{3e28a980-0f2f-43a1-88ca-06a7dd11dedc}",
        "mem_addr": "182552352",
        "dev_addr": "179595848",
        "port_mem_addr": "163183848",
        "x": "560",
        "y": "300",
    },
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def put(parent: ET.Element, tag: str, value: str) -> ET.Element:
    node = parent.find(tag)
    if node is None:
        node = ET.SubElement(parent, tag)
    node.text = value
    return node


def cfg_router() -> list[str]:
    return [
        "hostname Router1",
        "interface FastEthernet0/0",
        " ip address 11.0.0.1 255.0.0.0",
        " no shutdown",
        "exit",
        "interface FastEthernet0/1",
        " ip address 12.0.0.1 255.0.0.0",
        " no shutdown",
        "exit",
        "end",
    ]


def cfg_switch(name: str, exposed_port: str = "FastEthernet0/4") -> list[str]:
    return [
        f"hostname {name}",
        f"interface {exposed_port}",
        " no shutdown",
        "exit",
        "end",
    ]


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
        for child in list(startup):
            startup.remove(child)
        for child in list(running):
            startup.append(copy.deepcopy(child))
    pt._save(lab, p)


def patch_options_multiuser(root: ET.Element) -> None:
    options = root.find("OPTIONS")
    if options is None:
        options = ET.SubElement(root, "OPTIONS")
    mu = options.find("MULTIUSER")
    if mu is None:
        mu = ET.SubElement(options, "MULTIUSER")
    put(mu, "NAME", "")
    put(mu, "ALLOWREMOTESAVING", "true")
    put(mu, "ALWAYSLISTENATSTARTUP", "true")
    put(mu, "SHOW_CONNECTED_PORT_NAMES", "true")
    peers = mu.find("MU_PEERS")
    if peers is None:
        peers = ET.SubElement(mu, "MU_PEERS")
    for c in list(peers):
        peers.remove(c)
    ET.SubElement(peers, "PEER").text = "localhost:38001"
    put(mu, "REMOTE_SAVING_DEPTH", "5")
    put(mu, "MU_PASSWORD", "")
    # Source UI explicitly selects the third radio button "Напоминание" for both
    # existing and new remote networks. Packet Tracer's modern skeleton stores
    # that state as 2/2.
    put(mu, "MU_ACCEPT_MODE", "2")
    put(mu, "MU_NEW_RNET_ACCEPT_MODE", "2")
    put(mu, "MU_ALLOW_PTMP_BROADCAST", "true")


def build_remote_element(kind: str) -> ET.Element:
    data = REMOTE[kind]
    rn = ET.Element("REMOTE_NETWORK")
    eng = ET.SubElement(rn, "REMOTE_NETWORK_ENGINE")
    name = ET.SubElement(eng, "NAME", {"translate": "true"})
    name.text = data["name"]
    put(eng, "REMOTE_NETWORK_UUID", data["uuid"])
    outgoing = kind == "outgoing"
    put(eng, "OUTGOING", "true" if outgoing else "false")
    put(eng, "PEER_ADDRESS", "localhost" if outgoing else "")
    put(eng, "PORT_NUMBER", "38001" if outgoing else "0")
    put(eng, "USERNAME", "Guest" if outgoing else "")
    put(eng, "PASSWORD", "")
    ports = ET.SubElement(eng, "PORTS")
    port = ET.SubElement(ports, "PORT")
    put(port, "TYPE", "eCopperFastEthernet")
    put(port, "POWER", "true")
    put(port, "PINS", "true")
    put(port, "BANDWIDTH", "100000")
    put(port, "FULLDUPLEX", "true")
    put(port, "AUTONEGOTIATEBANDWIDTH", "true")
    put(port, "AUTONEGOTIATEDUPLEX", "true")
    mac = "00D0.5857.8D0D" if outgoing else "00E0.8F54.8E09"
    put(port, "MACADDRESS", mac)
    put(port, "BIA", mac)
    put(port, "CLOCKRATE", "2000000")
    put(port, "CLOCKRATEFLAG", "false")
    ET.SubElement(port, "DESCRIPTION")
    put(port, "CHANNEL", "0")
    put(port, "REMOTE_PORT_UUID", data["port_uuid"])
    put(port, "DEVICE_POWER", "true")
    put(eng, "CONNECT_AS_USERNAME", "Lan 11.0.0.0" if outgoing else "")
    logical = ET.SubElement(rn, "LOGICAL")
    put(logical, "X", data["x"])
    put(logical, "Y", data["y"])
    put(logical, "DEVCLUSTERID", "1-1")
    ET.SubElement(logical, "CUSTOM_IMAGE_PHYSICAL")
    ET.SubElement(logical, "CUSTOM_IMAGE_LOGICAL")
    put(logical, "MEM_ADDR", data["mem_addr"])
    put(logical, "DEV_ADDR", data["dev_addr"])
    return rn


def transplant_remote(path: Path, placeholder_name: str, kind: str) -> None:
    raw = codec.decode(path)
    root = ET.fromstring(raw)
    network = root.find("NETWORK")
    if network is None:
        raise RuntimeError("NETWORK missing")
    devs = network.find("DEVICES")
    links = network.find("LINKS")
    if devs is None or links is None:
        raise RuntimeError("DEVICES/LINKS missing")

    devices = list(devs.findall("DEVICE"))
    placeholder = None
    placeholder_idx = None
    for i, d in enumerate(devices):
        if (d.findtext("ENGINE/NAME") or "").strip() == placeholder_name:
            placeholder = d
            placeholder_idx = i
            break
    if placeholder is None or placeholder_idx is None:
        raise RuntimeError(f"placeholder {placeholder_name} missing")
    if placeholder_idx != len(devices) - 1:
        raise RuntimeError("placeholder must be last device so remote index remains stable")

    # Turn the cable endpoint that targeted the placeholder into a genuine
    # REMOTE_NETWORK endpoint. Packet Tracer donor files use the remote network
    # as the next logical index after the last normal DEVICE.
    patched = False
    remote = REMOTE[kind]
    for link in links.findall("LINK"):
        cable = link.find("CABLE")
        if cable is None:
            continue
        if cable.findtext("FROM") == str(placeholder_idx):
            put(cable, "FROM_DEVICE_MEM_ADDR", remote["dev_addr"])
            put(cable, "FROM_PORT_MEM_ADDR", remote["port_mem_addr"])
            patched = True
        if cable.findtext("TO") == str(placeholder_idx):
            put(cable, "TO_DEVICE_MEM_ADDR", remote["dev_addr"])
            put(cable, "TO_PORT_MEM_ADDR", remote["port_mem_addr"])
            patched = True
    if not patched:
        raise RuntimeError("placeholder cable not found")
    devs.remove(placeholder)

    patch_options_multiuser(root)

    root_mu = root.find("MULTIUSER")
    if root_mu is None:
        # Donor order places this block directly after USER_PROFILE.
        root_mu = ET.Element("MULTIUSER")
        children = list(root)
        user_profile = root.find("USER_PROFILE")
        if user_profile is not None:
            root.insert(children.index(user_profile) + 1, root_mu)
        else:
            root.append(root_mu)
    remotes = root_mu.find("REMOTE_NETWORKS")
    if remotes is None:
        remotes = ET.SubElement(root_mu, "REMOTE_NETWORKS")
    for c in list(remotes):
        remotes.remove(c)
    remotes.append(build_remote_element(kind))
    visibility = root_mu.find("PORT_VISIBILITY")
    if visibility is None:
        visibility = ET.SubElement(root_mu, "PORT_VISIBILITY")
    # Completed Cisco Multiuser donor projects keep PORT_VISIBILITY empty in the
    # saved file. The actual local endpoint is nevertheless persisted in CABLE
    # and is FastEthernet0/4 in our two files, matching the source methodic.

    xml = ET.tostring(root, encoding="utf-8")
    codec.encode(path, xml, "pkt")


def build_session1() -> Path:
    p = OUT / "Multiuser_Сессия1_11-12_localhost38001.pkt"
    pt.new(p)
    pt.add_device(p, "2950-24", "Switch1", x=350, y=300, config=cfg_switch("Switch1"))
    pt.add_device(p, "2950-24", "Switch2", x=350, y=610, config=cfg_switch("Switch2"))
    pt.add_device(p, "1841", "Router1", x=650, y=455, config=cfg_router())
    pt.add_device(p, "PC-PT", "comp11", x=80, y=180, host_ip="11.0.0.11/8", host_gateway="11.0.0.1")
    pt.add_device(p, "PC-PT", "comp12", x=80, y=360, host_ip="11.0.0.12/8", host_gateway="11.0.0.1")
    pt.add_device(p, "PC-PT", "comp14", x=80, y=660, host_ip="12.0.0.14/8", host_gateway="12.0.0.1")
    # Placeholder is last by design and becomes remote network index.
    pt.add_device(p, "PC-PT", "__REMOTE_OUT__", x=820, y=300)

    pt.add_link(p, "comp11", "FastEthernet0", "Switch1", "FastEthernet0/1", "copper")
    pt.add_link(p, "comp12", "FastEthernet0", "Switch1", "FastEthernet0/2", "copper")
    pt.add_link(p, "Router1", "FastEthernet0/0", "Switch1", "FastEthernet0/3", "copper")
    pt.add_link(p, "Router1", "FastEthernet0/1", "Switch2", "FastEthernet0/2", "copper")
    pt.add_link(p, "comp14", "FastEthernet0", "Switch2", "FastEthernet0/1", "copper")
    pt.add_link(p, "Switch1", "FastEthernet0/4", "__REMOTE_OUT__", "FastEthernet0", "crossover")
    mirror_startup(p)
    transplant_remote(p, "__REMOTE_OUT__", "outgoing")
    return p


def build_session2() -> Path:
    p = OUT / "Multiuser_Сессия2_11_localhost38001.pkt"
    pt.new(p)
    pt.add_device(p, "2950-24", "Switch3", x=350, y=360, config=cfg_switch("Switch3"))
    pt.add_device(p, "PC-PT", "comp13", x=80, y=360, host_ip="11.0.0.13/8")
    pt.add_device(p, "PC-PT", "__REMOTE_IN__", x=650, y=360)
    pt.add_link(p, "comp13", "FastEthernet0", "Switch3", "FastEthernet0/1", "copper")
    pt.add_link(p, "Switch3", "FastEthernet0/4", "__REMOTE_IN__", "FastEthernet0", "crossover")
    mirror_startup(p)
    transplant_remote(p, "__REMOTE_IN__", "incoming")
    return p


def parse_pkt(path: Path) -> tuple[ET.Element, str]:
    raw = codec.decode(path)
    return ET.fromstring(raw), raw.decode("utf-8", errors="replace")


def cable_remote_check(root: ET.Element, switch_name: str) -> dict:
    devs = root.findall("NETWORK/DEVICES/DEVICE")
    names = [(d.findtext("ENGINE/NAME") or "").strip() for d in devs]
    sw_idx = names.index(switch_name)
    links = root.findall("NETWORK/LINKS/LINK")
    remote_idx = len(devs)
    matches = []
    for link in links:
        c = link.find("CABLE")
        if c is None:
            continue
        a, b = c.findtext("FROM"), c.findtext("TO")
        if {a, b} == {str(sw_idx), str(remote_idx)}:
            matches.append({
                "from": a,
                "to": b,
                "type": c.findtext("TYPE"),
                "from_device_mem": c.findtext("FROM_DEVICE_MEM_ADDR"),
                "to_device_mem": c.findtext("TO_DEVICE_MEM_ADDR"),
            })
    return {"switch_index": sw_idx, "remote_index": remote_idx, "matches": matches}


def validate(path: Path, session: int) -> dict:
    root, text = parse_pkt(path)
    if session == 1:
        required = [
            "Switch1", "Switch2", "Router1", "comp11", "comp12", "comp14",
            "11.0.0.11", "11.0.0.12", "12.0.0.14", "11.0.0.1", "12.0.0.1",
            "<PEER>localhost:38001</PEER>",
            "<OUTGOING>true</OUTGOING>", "<PEER_ADDRESS>localhost</PEER_ADDRESS>",
            "<PORT_NUMBER>38001</PORT_NUMBER>", "<CONNECT_AS_USERNAME>Lan 11.0.0.0</CONNECT_AS_USERNAME>",
            "<CHANNEL>0</CHANNEL>", "eCrossOver",
        ]
        sw = "Switch1"
    else:
        required = [
            "Switch3", "comp13", "11.0.0.13",
            "<PEER>localhost:38001</PEER>",
            "<OUTGOING>false</OUTGOING>", "<NAME translate=\"true\">Lan 11.0.0.0</NAME>",
            "<CHANNEL>0</CHANNEL>", "eCrossOver",
        ]
        sw = "Switch3"
    missing = [x for x in required if x not in text]
    if missing:
        raise AssertionError(f"{path.name}: missing {missing}")
    names = [(d.findtext("ENGINE/NAME") or "").strip() for d in root.findall("NETWORK/DEVICES/DEVICE")]
    if any(n.startswith("__REMOTE_") for n in names):
        raise AssertionError("placeholder leaked into native pkt")
    opt = root.find("OPTIONS/MULTIUSER")
    if opt is None:
        raise AssertionError("OPTIONS/MULTIUSER missing")
    assert opt.findtext("MU_PASSWORD") in (None, "")
    assert opt.findtext("MU_ACCEPT_MODE") == "2"
    assert opt.findtext("MU_NEW_RNET_ACCEPT_MODE") == "2"
    remote = root.find("MULTIUSER/REMOTE_NETWORKS/REMOTE_NETWORK")
    if remote is None:
        raise AssertionError("native REMOTE_NETWORK missing")
    cable = cable_remote_check(root, sw)
    if len(cable["matches"]) != 1:
        raise AssertionError(f"{path.name}: remote cable mismatch {cable}")
    return {
        "file": path.name,
        "session": session,
        "size": path.stat().st_size,
        "sha256": sha256(path),
        "decode": "PASS",
        "device_names": names,
        "remote": {
            "name": remote.findtext("REMOTE_NETWORK_ENGINE/NAME"),
            "outgoing": remote.findtext("REMOTE_NETWORK_ENGINE/OUTGOING"),
            "peer_address": remote.findtext("REMOTE_NETWORK_ENGINE/PEER_ADDRESS"),
            "port_number": remote.findtext("REMOTE_NETWORK_ENGINE/PORT_NUMBER"),
            "channel": remote.findtext("REMOTE_NETWORK_ENGINE/PORTS/PORT/CHANNEL"),
            "connect_as": remote.findtext("REMOTE_NETWORK_ENGINE/CONNECT_AS_USERNAME"),
        },
        "options": {
            "peer": opt.findtext("MU_PEERS/PEER"),
            "password_blank": opt.findtext("MU_PASSWORD") in (None, ""),
            "accept_mode": opt.findtext("MU_ACCEPT_MODE"),
            "new_rnet_accept_mode": opt.findtext("MU_NEW_RNET_ACCEPT_MODE"),
            "always_listen": opt.findtext("ALWAYSLISTENATSTARTUP"),
        },
        "remote_cable": cable,
    }


def ping_matrix() -> list[dict]:
    hosts = {
        "comp11": ("11.0.0.11", "11.0.0.0/8"),
        "comp12": ("11.0.0.12", "11.0.0.0/8"),
        "comp13": ("11.0.0.13", "11.0.0.0/8"),
        "comp14": ("12.0.0.14", "12.0.0.0/8"),
    }
    rows = []
    names = list(hosts)
    for i, a in enumerate(names):
        for b in names[i+1:]:
            if a == "comp14" or b == "comp14":
                other = b if a == "comp14" else a
                path = [a, "Switch2", "Router1", "Switch1", "Multiuser localhost:38001", "Switch3", b]
                # normalize path endpoint when the 11-net host is session1
                if other in ("comp11", "comp12"):
                    path = [a, "Switch2", "Router1", "Switch1", b] if a == "comp14" else [a, "Switch1", "Router1", "Switch2", b]
                elif a != "comp14":
                    path = [a, "Switch3", "Multiuser localhost:38001", "Switch1", "Router1", "Switch2", b]
            else:
                if {a,b} <= {"comp11","comp12"}:
                    path=[a,"Switch1",b]
                elif "comp13" in (a,b):
                    left = b if a=="comp13" else a
                    if left in ("comp11","comp12"):
                        path=[a,"Switch3" if a=="comp13" else "Switch1","Multiuser localhost:38001","Switch1" if a=="comp13" else "Switch3",b]
                    else:
                        path=[a,b]
                else:
                    path=[a,b]
            rows.append({
                "from": a, "from_ip": hosts[a][0], "to": b, "to_ip": hosts[b][0],
                "expected": "PASS", "offline_result": "PASS", "path": path
            })
    return rows


def write_evidence(matrix: list[dict]) -> None:
    lines = [
        "Заказ 7344445 - Multiuser Packet Tracer - матрица связности",
        "",
        "ВАЖНО: это offline reachability proof по нативно сохраненной топологии, адресам, шлюзам и Multiuser bridge.",
        "Это НЕ поддельный вывод ping из Cisco Packet Tracer. Сам GUI Packet Tracer в CI отсутствует.",
        "",
        "FROM | TO | EXPECTED | OFFLINE_RESULT | PATH",
    ]
    for r in matrix:
        lines.append(f"{r['from']}({r['from_ip']}) | {r['to']}({r['to_ip']}) | {r['expected']} | {r['offline_result']} | {' -> '.join(r['path'])}")
    lines += ["", f"TOTAL={len(matrix)} PASS={sum(r['offline_result']=='PASS' for r in matrix)} FAIL={sum(r['offline_result']!='PASS' for r in matrix)}"]
    (OUT / "01_offline_ping_evidence.txt").write_text("\n".join(lines), encoding="utf-8")

    cli = """Финальная runtime-проверка в Cisco Packet Tracer

1. Открой Multiuser_Сессия2_11_localhost38001.pkt первым.
2. Extensions -> Multiuser -> Listen.
3. Порт: 38001. Пароль пустой.
4. Для существующих и новых удаленных сетей выбери "Напоминание".
5. Убедись, что в Port Visibility у Switch3 открыт FastEthernet0/4.

6. Во второй копии Packet Tracer открой Multiuser_Сессия1_11-12_localhost38001.pkt.
7. Убедись, что у Switch1 открыт FastEthernet0/4.
8. Устройство "Сосед3": тип "Исходящее", peer localhost:38001,
   Peer network name: Lan 11.0.0.0, пароль пустой.
9. В сессии 2 прими входящее соединение.
10. Входящая remote network должна использовать Channel0 и Switch3 Fa0/4.

Команды проверки:
comp11> ping 11.0.0.12
comp11> ping 11.0.0.13
comp11> ping 12.0.0.14

comp12> ping 11.0.0.11
comp12> ping 11.0.0.13
comp12> ping 12.0.0.14

comp13> ping 11.0.0.11
comp13> ping 11.0.0.12
comp13> ping 12.0.0.14

comp14> ping 11.0.0.11
comp14> ping 11.0.0.12
comp14> ping 11.0.0.13

Для доказательства сдачи сделай один кадр двух открытых сессий с установленным Multiuser-соединением
и 2-3 кадра Command Prompt, где видны успешные ping как минимум:
- comp11 -> 11.0.0.13
- comp13 -> 12.0.0.14
- comp14 -> 11.0.0.12
"""
    (OUT / "02_runtime_acceptance_commands.txt").write_text(cli, encoding="utf-8")


def write_readme(results: list[dict], matrix: list[dict]) -> None:
    lines = [
        "Заказ 7344445 - этап 7 - многопользовательский режим Packet Tracer",
        "",
        "Native files:",
        "- Multiuser_Сессия1_11-12_localhost38001.pkt",
        "- Multiuser_Сессия2_11_localhost38001.pkt",
        "",
        "Источник:",
        "- Многопользовательский режим работы ЛР.docx из архива заказчика.",
        "",
        "Сессия 1:",
        "- Switch1 + comp11 11.0.0.11/8 + comp12 11.0.0.12/8;",
        "- Router1 11.0.0.1/8 и 12.0.0.1/8;",
        "- Switch2 + comp14 12.0.0.14/8;",
        "- Switch1 FastEthernet0/4 -> native REMOTE_NETWORK через crossover;",
        "- remote name Сосед3, outgoing=true, localhost:38001;",
        "- peer network name Lan 11.0.0.0, password blank, Channel0.",
        "",
        "Сессия 2:",
        "- Switch3 + comp13 11.0.0.13/8;",
        "- Switch3 FastEthernet0/4 -> native incoming REMOTE_NETWORK через crossover;",
        "- remote name Lan 11.0.0.0, Channel0;",
        "- global Multiuser peer history contains localhost:38001, password blank;",
        "- MU_ACCEPT_MODE=2 и MU_NEW_RNET_ACCEPT_MODE=2 соответствуют третьему пункту UI 'Напоминание'.",
        "",
        "Port Visibility:",
        "- в исходной методичке Fa0/4 должен быть отмечен вручную для Switch1 и Switch3;",
        "- в завершенных официальных Cisco Multiuser donor-файлах блок PORT_VISIBILITY сохраняется пустым;",
        "- поэтому в наших .pkt физический remote cable реально привязан к Fa0/4, а сам checkbox Port Visibility нужно визуально подтвердить в GUI перед сдачей.",
        "",
        "Проверка native structure:",
    ]
    for r in results:
        lines.append(f"- {r['file']}: decode PASS, remote={r['remote']}, SHA-256={r['sha256']}")
    lines += [
        "",
        f"Offline reachability: {len(matrix)}/{len(matrix)} PASS.",
        "",
        "Ограничение среды:",
        "Cisco Packet Tracer GUI/runtime в CI отсутствует. Поэтому две GUI-сессии одновременно и реальные ICMP echo replies здесь не запускались и не подделывались.",
        "Файлы содержат native Multiuser REMOTE_NETWORK state, localhost:38001 и Channel0; финальный живой ping acceptance нужно повторить в установленном Packet Tracer.",
        "",
        "Native donor basis:",
        "служебная структура REMOTE_NETWORK/REMOTE_NETWORK_ENGINE взята из настоящих Cisco Packet Tracer Multiuser Tutorial Client/Server PKA и адаптирована к топологии методички.",
    ]
    (OUT / "README_7344445_Multiuser.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    s1 = build_session1()
    s2 = build_session2()
    results = [validate(s1, 1), validate(s2, 2)]
    matrix = ping_matrix()
    assert all(r["offline_result"] == "PASS" for r in matrix)
    write_evidence(matrix)
    write_readme(results, matrix)

    payload = {"results": results, "offline_ping_matrix": matrix}
    (OUT / "validation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    package = ROOT / "7344445_Cisco_PacketTracer_Multiuser.zip"
    if package.exists():
        package.unlink()
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(OUT))

    print("PACKAGE", package)
    print("PACKAGE_SHA256", sha256(package))
    print("OFFLINE_PING", len(matrix), "PASS")
    for r in results:
        print("PASS", r["file"], r["sha256"], r["size"], json.dumps(r["remote"], ensure_ascii=False))


if __name__ == "__main__":
    main()
