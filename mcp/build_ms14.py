import json, os, sys
from pathlib import Path

netlist_path=Path(sys.argv[1])
out_ms14=Path(sys.argv[2])
image_path=Path(sys.argv[3])
result_path=Path(sys.argv[4])

from multisim_mcp.server import create_schematic_from_netlist

netlist=netlist_path.read_text(encoding="utf-8")
positions={
    "VCTRL":[80,80],
    "R1":[220,80],"R2":[360,80],"D_VD1":[500,150],"C1":[580,150],"C2":[120,210],"D_VD2":[120,310],
    "M_VT1":[700,80],"M_VT2":[860,80],"R3":[700,230],"R4":[700,20],"R5":[860,20],
    "M_VT3":[1030,80],"R6":[1160,80],
    "R7":[180,470],"D_VD3":[330,470],"D_HL1":[470,470],
    "R_FU1":[1160,250],"D_BR1":[940,360],"D_BR2":[940,470],"D_BR3":[1080,360],"D_BR4":[1080,470],
    "R8":[760,420],"D_VD4":[760,530],"R9":[630,600],"D_VD5":[630,710],
    "S_VS1":[470,600],"S_VS2":[470,730],
    "R_RU1":[1160,480],"C3":[260,730],
    "VMAINS":[80,650],"R_FU2":[80,790],"RLOAD":[260,600],
}
try:
    result=create_schematic_from_netlist(
        netlist,
        str(out_ms14),
        open_after_build=True,
        image_path=str(image_path),
        overwrite=True,
        component_positions=positions,
        sheet_size=[1400,900],
        verify=True,
        require_layout_pass=False,
    )
    result_path.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
    if not out_ms14.exists():
        raise SystemExit(20)
except Exception as e:
    import traceback
    result_path.write_text(traceback.format_exc(),encoding="utf-8")
    traceback.print_exc()
    raise
