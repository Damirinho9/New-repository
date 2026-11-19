"""Compare decoded native electrical nodes with the locked source reference."""
import json,hashlib
from pathlib import Path
from multisimforge import check

EXPECTED={
"0": "C1.2 C2.2 R3.2 RU1.2 VD1.A VD2.A VD6.V+ VT3.G I1.1 RREF.2",
"u_ctrl":"R1.1 C2.1 R4.1 VD2.K R5.1 HL1.K",
"n_r1":"R1.2 R2.1",
"sens":"R2.2 VD1.K C1.1 VT1.S I1.2",
"t1":"VT1.D R4.2 VT2.S",
"g12":"VT1.G VT2.G R3.1",
"t2":"VT2.D R5.2 VT3.S",
"vt3_r6":"VT3.D R6.1",
"drv":"R6.2 RU1.1 FU1.1",
"led_a":"HL1.A VD3.K",
"led_r":"VD3.A R7.1",
"n_int":"VS1.K VS2.A R8.2 VD4.A C3.2 FU2.1 RREF.1",
"g18":"VS1.G R8.1 VD4.K VD6.AC1",
"br_top":"FU1.2 VD6.V-",
"g25":"VD6.AC2 VD5.K R9.1 VS2.G",
"sw":"VS1.A VS2.K VD5.A R9.2 XP1.P1 RLOAD.2",
"l":"R7.2 C3.1 XP1.P2 XP1.P3 RLINE.2 RLOAD.1",
"n":"FU2.2 XP1.P4 V1.2",
"nc_xp1":"XP1.P5",
"ac_src":"V1.1 RLINE.1"
}
SOURCE=set("R1 R2 VD1 C1 C2 VT1 R3 R4 VT2 VD2 R5 VT3 R6 HL1 VD3 RU1 R7 VS1 R8 VD4 FU1 VD6 VD5 R9 VS2 C3 FU2 XP1".split())
BENCH=set("I1 RREF V1 RLINE RLOAD".split())
def audit(path,manifest):
    path=Path(path)
    q=check.inspect(path); net={k:set(v) for k,v in q["nets"].items() if v}
    expected={k:set(v.split()) for k,v in EXPECTED.items()}
    diff={k:{"missing":sorted(expected.get(k,set())-net.get(k,set())),"extra":sorted(net.get(k,set())-expected.get(k,set()))} for k in expected.keys()|net.keys() if expected.get(k,set())!=net.get(k,set())}
    # Independent of part names: source components must occur exactly once and retain pins.
    refs=[x["refdes"] for x in q["components"]]
    missed=sorted(x for x in SOURCE if refs.count(x)!=1)
    extras=sorted(set(refs)-SOURCE-BENCH)
    problems=check.check_file(path)
    record={"result":"PASS_SOURCE_GRAPH" if not diff and not missed and not extras else "FAIL_SOURCE_GRAPH",
      "source_count":sum(x in SOURCE for x in refs),"missing_or_duplicate":missed,"extra_non_bench_components":extras,
      "net_differences":diff,"native_inspect":q,"geometry":problems,
      "model_notes":manifest["model_patch_notes"],"candidate_pin_hypotheses":manifest["source_ambiguous_assignments"],
      "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
      "native_gui_reopen":"NOT_RUN_IN_OFFLINE_STAGE","functional_simulation":"NOT_RUN_IN_OFFLINE_STAGE",
      "limitations":["D/S, RB154 and VD4 polarity are hypotheses; XP1 P5 is isolated in testbench, not a confirmed original contact assignment.",
      "R1's linked third terminal represented by effective 4.7M two-pin resistor; capacitor values assumptions.",
      "RU1 normal-state proxy, fuse 30A proxy, SCR functional model, not equipment protection validation."]}
    record["strict_structure_pass"]=record["result"]=="PASS_SOURCE_GRAPH" and not problems.get("problems")
    path.with_name("topology_audit.json").write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(record,ensure_ascii=False,indent=2))
    if not record["strict_structure_pass"]:raise SystemExit("STRUCTURE_OR_GRAPH_NOT_ACCEPTED")
