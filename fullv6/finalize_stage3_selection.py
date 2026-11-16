import csv, json, math, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/"stage3-final"
OUT.mkdir(parents=True,exist_ok=True)
scan=json.loads((ROOT/"stage3-out"/"stage3_scan_summary.json").read_text(encoding="utf-8"))
rows=[r for r in scan.get("results",[]) if r.get("metrics")]
if len(rows)<3:
    raise SystemExit("Not enough successful sweep points")
rows.sort(key=lambda r:r["photocurrent_uA"])
# Pick threshold by the largest real adjacent change in load RMS.
j=max(range(len(rows)-1),key=lambda i:abs(rows[i+1]["metrics"]["load_v"]["rms"]-rows[i]["metrics"]["load_v"]["rms"]))
jump=abs(rows[j+1]["metrics"]["load_v"]["rms"]-rows[j]["metrics"]["load_v"]["rms"])
if jump<1.0:
    raise SystemExit(f"No meaningful output transition found; largest load RMS jump only {jump:g} V")
threshold_uA=(rows[j]["photocurrent_uA"]+rows[j+1]["photocurrent_uA"])/2
states={"dark":rows[0]["photocurrent_uA"],"threshold":threshold_uA,"light":rows[-1]["photocurrent_uA"]}
print(json.dumps({"states":states,"largest_adjacent_load_rms_jump_V":jump},indent=2))

# Write a machine-readable selection file. The final workflow rebuilds and simulates these exact currents.
(OUT/"stage3_selected_currents.json").write_text(json.dumps({
    "selection_method":"dark=min scanned I_PH; light=max scanned I_PH; threshold=midpoint of adjacent scan pair with largest measured load-RMS change",
    "states_uA":states,
    "largest_adjacent_load_rms_jump_V":jump,
    "bracket_uA":[rows[j]["photocurrent_uA"],rows[j+1]["photocurrent_uA"]],
    "bracket_load_rms_V":[rows[j]["metrics"]["load_v"]["rms"],rows[j+1]["metrics"]["load_v"]["rms"]]
},ensure_ascii=False,indent=2),encoding="utf-8")
