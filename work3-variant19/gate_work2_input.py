# -*- coding: utf-8 -*-
"""Strict input gate for Work 3.

Work 3 is allowed to consume only the accepted artifact produced by the
Work 2 native workflow. This script verifies acceptance markers, the three
native model files and SHA-256 before any KOMPAS drawing code is started.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
import json
import re
import sys
import zipfile

HERE = Path(__file__).resolve().parent
INPUT = HERE / "input"
OUT = HERE / "native"
SOURCE_JSON = OUT / "source-work2.json"

WORKPIECE = INPUT / "Work2_V19_Workpiece.m3d"
CUTTER = INPUT / "Work2_V19_FormCutter.m3d"
ASSEMBLY = INPUT / "Work2_V19_TopDown.a3d"
ACCEPTANCE = INPUT / "ACCEPTANCE.txt"
VERIFICATION = INPUT / "verification.txt"
HASHES = INPUT / "SHA256.txt"

REQUIRED_VERIFY = (
    "WORKPIECE_REOPEN_PASS",
    "CUTTER_REOPEN_PASS",
    "ASSEMBLY_REOPEN_PASS",
    "TOP_DOWN_DEPENDENCY_PHYSICAL_CHANGE_PASS",
    "TOP_DOWN_DEPENDENCY_RESTORE_PASS",
    "FINAL_NOMINAL_REOPEN_PASS",
    "RESULT=PASS_NATIVE_WORK2_VARIANT19_REOPEN_REBUILD_DEPENDENCY",
)


def require(value, message):
    if not value:
        raise RuntimeError(message)
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_kompas(path: Path):
    require(path.exists() and path.stat().st_size > 1024, f"{path.name}: missing/small")
    require(zipfile.is_zipfile(path), f"{path.name}: not a native modern KOMPAS container")
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        require("Contents" in names and "FileInfo" in names,
                f"{path.name}: native Contents/FileInfo missing")


def expected_hashes(text: str):
    out = {}
    # PowerShell Format-Table output from Work 2 contains SHA256 and path.
    for line in text.splitlines():
        m = re.search(r"([0-9A-Fa-f]{64})\s+(.+?\.(?:m3d|a3d))\s*$", line)
        if m:
            out[Path(m.group(2).strip()).name.lower()] = m.group(1).lower()
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    require(ACCEPTANCE.exists(), "Work 2 ACCEPTANCE.txt is missing")
    require(VERIFICATION.exists(), "Work 2 verification.txt is missing")
    require(HASHES.exists(), "Work 2 SHA256.txt is missing")

    acc = ACCEPTANCE.read_text(encoding="utf-8-sig", errors="replace")
    verify = VERIFICATION.read_text(encoding="utf-8-sig", errors="replace")
    require("RESULT=PASS_NATIVE_WORK2_VARIANT19" in acc,
            "Work 2 final acceptance marker is absent")
    for marker in REQUIRED_VERIFY:
        require(marker in verify, f"Work 2 verification marker absent: {marker}")

    for p in (WORKPIECE, CUTTER, ASSEMBLY):
        native_kompas(p)

    actual = {p.name: sha256(p) for p in (WORKPIECE, CUTTER, ASSEMBLY)}
    expected = expected_hashes(HASHES.read_text(encoding="utf-8-sig", errors="replace"))
    require(len(expected) >= 3, "Could not parse all Work 2 hashes")
    for name, digest in actual.items():
        require(expected.get(name.lower()) == digest.lower(),
                f"Work 2 SHA mismatch for {name}")

    payload = {
        "variant": 19,
        "source_contract": "accepted Work 2 artifact only",
        "artifact_name": "7335493-work2-variant19-native-top-down",
        "files": actual,
        "required_verification_markers": list(REQUIRED_VERIFY),
        "result": "WORK2_ACCEPTED_INPUT_PASS",
    }
    SOURCE_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("WORK2_ACCEPTED_INPUT_PASS")
    print(f"SOURCE_CUTTER_SHA256={actual[CUTTER.name]}")
    print("RESULT=PASS_WORK3_INPUT_GATE")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("RESULT=FAIL_WORK3_INPUT_GATE", file=sys.stderr)
        print(repr(exc), file=sys.stderr)
        raise
