from __future__ import annotations

import base64
import copy
import gzip
import hashlib
import json
import os
import shutil
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from ptlab import codec
from ptlab import lab as pt
from ptlab import library
from ptlab import vendorlib

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "out"
OUT.mkdir(parents=True, exist_ok=True)

DONOR = Path(os.environ.get("DONOR_DIR", "/tmp/donor"))
HWIC_DONOR = Path(os.environ.get("HWIC_DONOR_DIR", "/tmp/hwic-donor"))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def put(parent: ET.Element, tag: str, value: str) -> None:
    node = parent.find(tag)
    if node is None:
        node = ET.SubElement(parent, tag)
    node.text = value


def install_harvested_module() -> dict:
    """Harvest HWIC-4ESW from a real Packet Tracer donor and merge into PTLAB_LIB."""
    api = vendorlib.lab_api()
    found = api.harvest_modules(str(HWIC_DONOR), {"HWIC-4ESW"})
    if "HWIC-4ESW" not in found:
        raise RuntimeError("HWIC-4ESW was not found in the donor Packet Tracer project")

    lib = vendorlib.lib_path()
    lib.parent.mkdir(parents=True, exist_ok=True)
    data = json.loads(lib.read_text(encoding="utf-8")) if lib.exists() else {}
    data.setdefault("gz", True)
    data.setdefault("models", {})
    data.setdefault("modules", {})
    raw = found["HWIC-4ESW"]
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    data["modules"]["HWIC-4ESW"] = base64.b64encode(gzip.compress(raw, 9)).decode("ascii")
    lib.write_text(json.dumps(data), encoding="utf-8")
    return {"module": "HWIC-4ESW", "source": str(HWIC_DONOR), "library": str(lib)}


def prepare_local_library() -> dict:
    donor_lr1 = DONOR / "4.pkt"
    if not donor_lr1.exists():
        raise FileNotFoundError(donor_lr1)
    harvested = library.harvest(donor_lr1, wanted={"Printer-PT"}, save=True)
    module = install_harvested_module()
    catalog = pt.models()
    model_names = {x["model"] for x in catalog["models"]}
    assert "Printer-PT" in model_names, "Printer-PT not present after harvest"
    assert "HWIC-4ESW" in catalog["modules"], "HWIC-4ESW not present after harvest"
    return {"printer": harvested, "hwic": module}


def clear_dns(path: Path, server: str) -> None:
    lab, p = pt._lab(path)
    el = pt._device(lab, server)
    dns = next(el.iter("DNS_SERVER"), None)
    if dns is None:
        raise RuntimeError(f"{server}: DNS_SERVER missing")
    put(dns, "ENABLED", "1")
    db = dns.find("NAMESERVER-DATABASE")
    if db is None:
        db = ET.SubElement(dns, "NAMESERVER-DATABASE")
    for child in list(db):
        db.remove(child)
    pt._save(lab, p)


def patch_http_index(path: Path, server: str, html: str) -> None:
    lab, p = pt._lab(path)
    el = pt._device(lab, server)
    http = next(el.iter("HTTP_SERVER"), None)
    if http is None:
        raise RuntimeError(f"{server}: HTTP_SERVER missing")
    put(http, "ENABLED", "1")
    patched = 0
    for files_el in el.iter("FILES"):
        files = files_el.findall("FILE")
        if not any((f.findtext("NAME") or "").lower() == "index.html" for f in files):
            continue
        for f in files:
            if (f.findtext("NAME") or "").lower() == "index.html":
                fc = f.find("FILE_CONTENT")
                if fc is None:
                    fc = ET.SubElement(f, "FILE_CONTENT")
                put(fc, "TEXT", html)
                patched += 1
    if not patched:
        raise RuntimeError(f"{server}: index.html filesystem not found")
    pt._save(lab, p)


def patch_dhcp_pool_exact(path: Path, server: str) -> None:
    lab, p = pt._lab(path)
    el = pt._device(lab, server)
    dhcp = next(el.iter("DHCP_SERVER"), None)
    if dhcp is None:
        raise RuntimeError(f"{server}: DHCP_SERVER missing")
    put(dhcp, "ENABLED", "1")
    pools = dhcp.find("POOLS")
    if pools is None:
        pools = ET.SubElement(dhcp, "POOLS")
    existing = pools.findall("POOL")
    if not existing:
        pool = ET.SubElement(pools, "POOL")
    else:
        pool = existing[0]
        for extra in existing[1:]:
            pools.remove(extra)
    values = {
        "NAME": "serverPool",
        "NETWORK": "10.0.0.0",
        "MASK": "255.0.0.0",
        "DEFAULT_ROUTER": "0.0.0.0",
        "TFTP_ADDRESS": "0.0.0.0",
        "START_IP": "10.0.0.10",
        "END_IP": "10.0.0.14",
        "DNS_SERVER": "10.0.0.1",
        "MAX_USERS": "5",
    }
    for tag, value in values.items():
        put(pool, tag, value)
    pt._save(lab, p)


def replace_config(path: Path, device: str, lines: list[str]) -> None:
    lab, p = pt._lab(path)
    el = pt._device(lab, device)
    eng = el.find("ENGINE")
    if eng is None:
        raise RuntimeError(f"{device}: ENGINE missing")
    for tag in ("RUNNINGCONFIG", "STARTUPCONFIG"):
        cfg = eng.find(tag)
        if cfg is None:
            cfg = ET.SubElement(eng, tag)
        for child in list(cfg):
            cfg.remove(child)
        for line in lines:
            ET.SubElement(cfg, "LINE").text = line
    pt._save(lab, p)


def build_interface() -> Path:
    p = OUT / "00_Интерфейс_Cisco_1841_HWIC-4ESW.pkt"
    pt.new(p)
    pt.add_device(
        p, "1841", "Router-1841",
        x=500, y=350, power=True,
        install="HWIC-4ESW", bay=0
    )
    return p


def build_ios_intro() -> Path:
    p = OUT / "00_IOS_базовые_команды.pkt"
    pt.new(p)
    cfg = [
        "hostname Router1",
        "enable password parol",
        "interface FastEthernet0/0",
        " description Ethernet interface on Router 1",
        " no shutdown",
        "exit",
        "end",
    ]
    pt.add_device(p, "1841", "Router1", x=500, y=350, config=cfg)
    return p


def build_lr1() -> Path:
    p = OUT / "ЛР01_Режим_симуляции.pkt"
    pt.new(p)

    pt.add_device(p, "Hub-PT", "Hub-Left", x=420, y=380)
    pt.add_device(p, "Hub-PT", "Main-Hub", x=760, y=380)

    pt.add_device(p, "Server-PT", "Server", x=920, y=180, host_ip="192.168.0.1/24")
    pt.add_device(p, "PC-PT", "PC2", x=180, y=180, host_ip="192.168.0.2/24")
    pt.add_device(p, "PC-PT", "PC3", x=180, y=330, host_ip="192.168.0.3/24")
    pt.add_device(p, "PC-PT", "PC4", x=180, y=500, host_ip="192.168.0.4/24")
    pt.add_device(p, "PC-PT", "PC5", x=930, y=420, host_ip="192.168.0.5/24")
    pt.add_device(p, "Printer-PT", "Printer", x=920, y=610, host_ip="192.168.0.10/24")

    pt.add_link(p, "Hub-Left", "FastEthernet0", "Main-Hub", "FastEthernet0", kind="crossover")
    pt.add_link(p, "PC2", "FastEthernet0", "Hub-Left", "FastEthernet1", kind="copper")
    pt.add_link(p, "PC3", "FastEthernet0", "Hub-Left", "FastEthernet2", kind="copper")
    pt.add_link(p, "PC4", "FastEthernet0", "Hub-Left", "FastEthernet3", kind="copper")
    pt.add_link(p, "Server", "FastEthernet0", "Main-Hub", "FastEthernet1", kind="copper")
    pt.add_link(p, "PC5", "FastEthernet0", "Main-Hub", "FastEthernet2", kind="copper")
    pt.add_link(p, "Printer", "FastEthernet0", "Main-Hub", "FastEthernet3", kind="copper")
    return p


def build_lr2() -> Path:
    p = OUT / "ЛР02_DNS_Web_DHCP.pkt"
    pt.new(p)

    pt.add_device(p, "PC-PT", "PC1", x=180, y=390)
    pt.add_device(p, "2950-24", "Switch1", x=520, y=390)
    pt.add_device(p, "Server-PT", "Server1", x=850, y=220, host_ip="10.0.0.1/8")
    pt.add_device(p, "Server-PT", "Server2", x=850, y=550, host_ip="10.0.0.2/8")

    pt.add_link(p, "PC1", "FastEthernet0", "Switch1", "FastEthernet0/1", kind="copper")
    pt.add_link(p, "Server1", "FastEthernet0", "Switch1", "FastEthernet0/2", kind="copper")
    pt.add_link(p, "Server2", "FastEthernet0", "Switch1", "FastEthernet0/3", kind="copper")

    pt.set_dhcp(p, "PC1", True)

    pt.set_service(p, "Server1", "dns", True)
    pt.set_service(p, "Server1", "http", True)
    pt.set_service(p, "Server1", "dhcp", False)
    clear_dns(p, "Server1")
    pt.add_dns_record(p, "Server1", "server1.rambler.ru", "10.0.0.1", record_type="A-REC")
    pt.add_dns_record(p, "Server1", "www.rambler.ru", "server1.rambler.ru", record_type="CNAME")

    html = """<html>
<center><font size='+2' color='blue'>Cisco Packet Tracer</font></center>

WWW.RAMBLER.RU
<p>
Server1

</html>"""
    patch_http_index(p, "Server1", html)

    pt.set_service(p, "Server2", "dhcp", True)
    pt.set_service(p, "Server2", "dns", False)
    pt.set_service(p, "Server2", "http", False)
    pt.add_dhcp_pool(
        p, "Server2", "10.0.0.0/8", "0.0.0.0",
        mask="255.0.0.0", dns="10.0.0.1",
        start_ip="10.0.0.10", name="serverPool", max_users=5
    )
    patch_dhcp_pool_exact(p, "Server2")
    return p


def build_lr3() -> Path:
    p = OUT / "ЛР03_Основные_команды_IOS.pkt"
    pt.new(p)

    r1 = [
        "hostname Router1",
        "enable password parol",
        "interface FastEthernet0/0",
        " description Ethernet interface on Router 1",
        " no shutdown",
        "exit",
        "interface Serial0/0/0",
        " clock rate 64000",
        " no shutdown",
        "exit",
        "end",
    ]
    r2 = [
        "hostname Router2",
        "interface FastEthernet0/0",
        " no shutdown",
        "exit",
        "interface Serial0/0/0",
        " no shutdown",
        "exit",
        "end",
    ]
    pt.add_device(p, "1841", "Router1", x=350, y=390, config=r1, install="WIC-2T", bay=0)
    pt.add_device(p, "1841", "Router2", x=760, y=390, config=r2, install="WIC-2T", bay=0)
    pt.add_link(p, "Router1", "FastEthernet0/0", "Router2", "FastEthernet0/0", kind="crossover")
    return p


def decoded_text(path: Path) -> str:
    return codec.decode(path).decode("utf-8", errors="replace")


def require(text: str, *needles: str) -> list[str]:
    missing = [x for x in needles if x not in text]
    if missing:
        raise AssertionError("missing: " + ", ".join(missing))
    return list(needles)


def validate(path: Path, kind: str) -> dict:
    text = decoded_text(path)
    info = pt.inspect(path)
    record = {
        "file": path.name,
        "kind": kind,
        "size": path.stat().st_size,
        "sha256": sha256(path),
        "decode": "PASS",
        "inspect": info,
        "checks": [],
    }

    if kind == "interface":
        record["checks"] = require(text, 'model="1841"', "<MODEL>HWIC-4ESW</MODEL>")
    elif kind == "ios":
        record["checks"] = require(
            text, 'model="1841"', "hostname Router1", "enable password parol",
            "interface FastEthernet0/0", "description Ethernet interface on Router 1", "no shutdown"
        )
    elif kind == "lr1":
        record["checks"] = require(
            text, 'model="Printer-PT"', "192.168.0.1", "192.168.0.2", "192.168.0.3",
            "192.168.0.4", "192.168.0.5", "192.168.0.10", "eCrossOver"
        )
        assert len(info["links"]) == 7, f"LR1 expected 7 links, got {len(info['links'])}"
    elif kind == "lr2":
        record["checks"] = require(
            text, 'model="2950-24"', "10.0.0.1", "10.0.0.2",
            "<TYPE>A-REC</TYPE>", "<NAME>server1.rambler.ru</NAME>",
            "<TYPE>CNAME</TYPE>", "<NAME>www.rambler.ru</NAME>",
            "<START_IP>10.0.0.10</START_IP>", "<END_IP>10.0.0.14</END_IP>",
            "<DNS_SERVER>10.0.0.1</DNS_SERVER>", "<MAX_USERS>5</MAX_USERS>",
            "WWW.RAMBLER.RU", "Cisco Packet Tracer"
        )
        assert len(info["links"]) == 3, f"LR2 expected 3 links, got {len(info['links'])}"
        pc = next(d for d in info["devices"] if d["name"] == "PC1")
        assert pc.get("dhcp") is True, "PC1 must be DHCP client"
    elif kind == "lr3":
        record["checks"] = require(
            text, 'model="1841"', "hostname Router1", "hostname Router2",
            "enable password parol", "interface FastEthernet0/0",
            "description Ethernet interface on Router 1", "clock rate 64000",
            "<MODEL>WIC-2T</MODEL>", "eCrossOver"
        )
        assert len(info["links"]) == 1, f"LR3 expected 1 Ethernet link, got {len(info['links'])}"
    else:
        raise ValueError(kind)

    return record


def write_readme(results: list[dict], library_info: dict) -> None:
    lines = [
        "Заказ 7344445 - базовый блок Cisco Packet Tracer",
        "",
        "Комплект:",
        "1. 00_Интерфейс_Cisco_1841_HWIC-4ESW.pkt - Cisco 1841 с реально установленным модулем HWIC-4ESW.",
        "2. 00_IOS_базовые_команды.pkt - базовая конфигурация IOS из вводного материала.",
        "3. ЛР01_Режим_симуляции.pkt - 2 хаба, Server, Printer, PC .2-.5, межхабовый crossover.",
        "4. ЛР02_DNS_Web_DHCP.pkt - Server1 DNS+HTTP, Server2 DHCP, PC1 DHCP.",
        "5. ЛР03_Основные_команды_IOS.pkt - Router1/Router2, password parol, Ethernet up, WIC-2T.",
        "",
        "ЛР2 точные значения:",
        "- Server1 10.0.0.1/8",
        "- Server2 10.0.0.2/8",
        "- A: server1.rambler.ru -> 10.0.0.1",
        "- CNAME: www.rambler.ru -> server1.rambler.ru",
        "- DHCP: 10.0.0.10-10.0.0.14, DNS 10.0.0.1, max users 5",
        "- index.html содержит Cisco Packet Tracer / WWW.RAMBLER.RU / Server1",
        "",
        "Важно по ЛР3:",
        "В исходной методичке последовательный интерфейс ошибочно назван fa0/1, хотя далее используются DCE и clock rate.",
        "В файле реализован технически корректный замысел на Serial0/0/0 через WIC-2T.",
        "Serial-кабель намеренно не добавлен: в текущем проверенном офлайн-генераторе serial-link имеет известную несовместимость с Packet Tracer 9.0.1.",
        "Основное Ethernet-соединение Router1-Router2 реально создано crossover и оба Fa0/0 включены.",
        "",
        "Проверка:",
        "Каждый .pkt после записи повторно декодирован нативным codec и проинспектирован.",
        "Это подтверждает структуру файла, устройства, конфигурацию и сервисы.",
        "Запуск ICMP/DNS/DHCP/HTTP внутри самого графического Packet Tracer в этом CI-контейнере невозможен, поэтому перед окончательной отправкой в Hexlet рекомендуется открыть файлы в установленном Packet Tracer и выполнить контрольные действия из методички.",
        "",
        "SHA-256:",
    ]
    for r in results:
        lines.append(f"- {r['file']}: {r['sha256']}")
    (OUT / "README_7344445.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    for p in OUT.iterdir():
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            shutil.rmtree(p)

    library_info = prepare_local_library()

    jobs = [
        (build_interface(), "interface"),
        (build_ios_intro(), "ios"),
        (build_lr1(), "lr1"),
        (build_lr2(), "lr2"),
        (build_lr3(), "lr3"),
    ]
    results = [validate(path, kind) for path, kind in jobs]

    (OUT / "validation.json").write_text(
        json.dumps({"library": library_info, "results": results}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    write_readme(results, library_info)

    package = ROOT / "7344445_Cisco_PacketTracer_Базовый_блок.zip"
    if package.exists():
        package.unlink()
    with zipfile.ZipFile(package, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(OUT.iterdir()):
            z.write(p, p.name)
    print("PACKAGE", package)
    print("PACKAGE_SHA256", sha256(package))
    for r in results:
        print("PASS", r["kind"], r["file"], r["sha256"], r["size"])


if __name__ == "__main__":
    main()
