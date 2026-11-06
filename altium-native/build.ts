import { CircuitJsonToAltiumConverter } from "circuit-json-to-altium"
import { serializeAltiumPcbDocWithKeepoutRules } from "circuit-json-to-altium/lib/serialize-altium-pcb-doc-with-keepout-rules"
import {
  getDanglingPcbReferences,
  parseAltiumBinaryPcbDoc,
  parseAltiumPrjPcb,
  parseAltiumSchDoc,
  validateAltiumDocument,
} from "altiumts"
import JSZip from "jszip"
import { createHash } from "node:crypto"
import { mkdir } from "node:fs/promises"

type Pin = { name: string; net: string }
type ComponentSpec = {
  ref: string
  value: string
  pins: Pin[]
  schX: number
  schY: number
  pcbX: number
  pcbY: number
  through: boolean
  pcbW?: number
  pcbH?: number
}

type FootprintSpec = {
  name: string
  mounting: "SMD" | "THT" | "EXTERNAL"
  width: number
  height: number
  padOffsets: { x: number; y: number }[]
  smdPad?: { width: number; height: number }
  holeDiameter?: number
  padDiameter?: number
  note: string
}

const components: ComponentSpec[] = [
  {ref:"R1", value:"4.7 MOhm", pins:[{name:"1",net:"U_CTRL"},{name:"2",net:"N_R1"}], schX:-18,schY:12,pcbX:-40,pcbY:27,through:false},
  {ref:"R2", value:"47 kOhm", pins:[{name:"1",net:"N_R1"},{name:"2",net:"SENS"}], schX:-12,schY:12,pcbX:-28,pcbY:27,through:false},
  {ref:"VD1", value:"FD320", pins:[{name:"A",net:"COM"},{name:"K",net:"SENS"}], schX:-6,schY:12,pcbX:-16,pcbY:27,through:true},
  {ref:"C1", value:"K50-35 0.47uF model", pins:[{name:"-",net:"COM"},{name:"+",net:"SENS"}], schX:0,schY:12,pcbX:-4,pcbY:27,through:true},
  {ref:"C2", value:"K73 0.1uF model", pins:[{name:"1",net:"U_CTRL"},{name:"2",net:"COM"}], schX:6,schY:12,pcbX:8,pcbY:27,through:false},
  {ref:"VD2", value:"KS512A ~12V", pins:[{name:"A",net:"COM"},{name:"K",net:"U_CTRL"}], schX:12,schY:12,pcbX:20,pcbY:27,through:true},

  {ref:"VT1", value:"KP501A", pins:[{name:"D",net:"SENS"},{name:"S",net:"T1"},{name:"G",net:"G12"}], schX:-18,schY:6,pcbX:-40,pcbY:15,through:false},
  {ref:"R3", value:"330 Ohm", pins:[{name:"1",net:"G12"},{name:"2",net:"COM"}], schX:-12,schY:6,pcbX:-28,pcbY:15,through:false},
  {ref:"R4", value:"10 kOhm", pins:[{name:"1",net:"U_CTRL"},{name:"2",net:"T1"}], schX:-6,schY:6,pcbX:-16,pcbY:15,through:false},
  {ref:"VT2", value:"KP501A", pins:[{name:"D",net:"T1"},{name:"S",net:"T2"},{name:"G",net:"G12"}], schX:0,schY:6,pcbX:-4,pcbY:15,through:false},
  {ref:"R5", value:"5.1 kOhm", pins:[{name:"1",net:"U_CTRL"},{name:"2",net:"T2"}], schX:6,schY:6,pcbX:8,pcbY:15,through:false},
  {ref:"VT3", value:"KP707B2", pins:[{name:"D",net:"VT3_R6"},{name:"S",net:"T2"},{name:"G",net:"COM"}], schX:12,schY:6,pcbX:20,pcbY:15,through:true},
  {ref:"R6", value:"51 Ohm", pins:[{name:"1",net:"VT3_R6"},{name:"2",net:"DRV"}], schX:18,schY:6,pcbX:34,pcbY:15,through:false},

  {ref:"R7", value:"58 kOhm", pins:[{name:"1",net:"L"},{name:"2",net:"LED_R"}], schX:-18,schY:0,pcbX:-40,pcbY:3,through:false},
  {ref:"VD3", value:"KD243ZH", pins:[{name:"A",net:"LED_R"},{name:"K",net:"LED_A"}], schX:-12,schY:0,pcbX:-28,pcbY:3,through:true},
  {ref:"HL1", value:"L383SRWT", pins:[{name:"A",net:"LED_A"},{name:"K",net:"U_CTRL"}], schX:-6,schY:0,pcbX:-16,pcbY:3,through:true},
  {ref:"RU1", value:"FNR-20K391", pins:[{name:"1",net:"DRV"},{name:"2",net:"COM"}], schX:0,schY:0,pcbX:-4,pcbY:3,through:true},
  {ref:"FU1", value:"32 A", pins:[{name:"1",net:"DRV"},{name:"2",net:"BR_A"}], schX:6,schY:0,pcbX:8,pcbY:3,through:true},
  {ref:"VD6", value:"RB154 bridge", pins:[{name:"~1",net:"BR_A"},{name:"~2",net:"COM"},{name:"+",net:"G1"},{name:"-",net:"G2"}], schX:12,schY:0,pcbX:22,pcbY:3,through:true,pcbW:5,pcbH:5},

  {ref:"R8", value:"56 Ohm", pins:[{name:"1",net:"G1"},{name:"2",net:"COM"}], schX:-18,schY:-6,pcbX:-40,pcbY:-10,through:false},
  {ref:"VD4", value:"KD243ZH", pins:[{name:"A",net:"COM"},{name:"K",net:"G1"}], schX:-12,schY:-6,pcbX:-28,pcbY:-10,through:true},
  {ref:"VS1", value:"T123-250", pins:[{name:"A",net:"SW"},{name:"K",net:"COM"},{name:"G",net:"G1"}], schX:-6,schY:-6,pcbX:-14,pcbY:-10,through:true,pcbW:6,pcbH:4},
  {ref:"R9", value:"56 Ohm", pins:[{name:"1",net:"G2"},{name:"2",net:"SW"}], schX:0,schY:-6,pcbX:0,pcbY:-10,through:false},
  {ref:"VD5", value:"KD243ZH", pins:[{name:"A",net:"SW"},{name:"K",net:"G2"}], schX:6,schY:-6,pcbX:12,pcbY:-10,through:true},
  {ref:"VS2", value:"T123-250", pins:[{name:"A",net:"COM"},{name:"K",net:"SW"},{name:"G",net:"G2"}], schX:12,schY:-6,pcbX:26,pcbY:-10,through:true,pcbW:6,pcbH:4},

  {ref:"C3", value:"K73 0.047uF model", pins:[{name:"1",net:"L"},{name:"2",net:"COM"}], schX:-12,schY:-12,pcbX:-28,pcbY:-24,through:true},
  {ref:"FU2", value:"32 A", pins:[{name:"1",net:"COM"},{name:"2",net:"N"}], schX:-4,schY:-12,pcbX:-12,pcbY:-24,through:true},
  {ref:"XP1", value:"MRN-5Sh 5-pin", pins:[{name:"1 SW",net:"SW"},{name:"2 LOAD",net:"L"},{name:"3 MAINS_L",net:"L"},{name:"4 MAINS_N",net:"N"},{name:"5 CASE",net:"CASE"}], schX:6,schY:-12,pcbX:12,pcbY:-24,through:true,pcbW:10,pcbH:4},
]

const footprints: Record<string, FootprintSpec> = {
  R1:  {name:"R_1206_3216Metric",mounting:"SMD",width:3.2,height:1.6,padOffsets:[{x:-1.4,y:0},{x:1.4,y:0}],smdPad:{width:1.4,height:1.8},note:"4.7 MOhm control resistor; 1206 gives more voltage margin than 0805."},
  R2:  {name:"R_0805_2012Metric",mounting:"SMD",width:2.0,height:1.25,padOffsets:[{x:-1.0,y:0},{x:1.0,y:0}],smdPad:{width:1.2,height:1.4},note:"Low-power control resistor."},
  R3:  {name:"R_0805_2012Metric",mounting:"SMD",width:2.0,height:1.25,padOffsets:[{x:-1.0,y:0},{x:1.0,y:0}],smdPad:{width:1.2,height:1.4},note:"Low-power gate/control resistor."},
  R4:  {name:"R_0805_2012Metric",mounting:"SMD",width:2.0,height:1.25,padOffsets:[{x:-1.0,y:0},{x:1.0,y:0}],smdPad:{width:1.2,height:1.4},note:"Low-power control resistor."},
  R5:  {name:"R_0805_2012Metric",mounting:"SMD",width:2.0,height:1.25,padOffsets:[{x:-1.0,y:0},{x:1.0,y:0}],smdPad:{width:1.2,height:1.4},note:"Low-power control resistor."},
  R6:  {name:"R_1206_3216Metric",mounting:"SMD",width:3.2,height:1.6,padOffsets:[{x:-1.4,y:0},{x:1.4,y:0}],smdPad:{width:1.4,height:1.8},note:"Gate-drive resistor with extra pulse-power margin."},
  R7:  {name:"R_2512_6332Metric_HV",mounting:"SMD",width:6.3,height:3.2,padOffsets:[{x:-3.0,y:0},{x:3.0,y:0}],smdPad:{width:1.8,height:3.3},note:"Line-side LED resistor; 2512 selected for power/voltage margin."},
  R8:  {name:"R_1206_3216Metric",mounting:"SMD",width:3.2,height:1.6,padOffsets:[{x:-1.4,y:0},{x:1.4,y:0}],smdPad:{width:1.4,height:1.8},note:"Thyristor gate network."},
  R9:  {name:"R_1206_3216Metric",mounting:"SMD",width:3.2,height:1.6,padOffsets:[{x:-1.4,y:0},{x:1.4,y:0}],smdPad:{width:1.4,height:1.8},note:"Thyristor gate network."},

  C1:  {name:"CP_Radial_D5.0mm_P2.00mm",mounting:"THT",width:5.0,height:5.0,padOffsets:[{x:-1.0,y:0},{x:1.0,y:0}],holeDiameter:0.8,padDiameter:1.8,note:"K50-35 electrolytic, radial through-hole."},
  C2:  {name:"C_Rect_L7.2mm_W2.5mm_P5.00mm",mounting:"THT",width:7.2,height:2.5,padOffsets:[{x:-2.5,y:0},{x:2.5,y:0}],holeDiameter:0.8,padDiameter:1.8,note:"K73 film capacitor; retained as THT rather than forcing SMD."},
  C3:  {name:"C_Rect_L18.0mm_W5.0mm_P15.00mm_HV",mounting:"THT",width:18.0,height:5.0,padOffsets:[{x:-7.5,y:0},{x:7.5,y:0}],holeDiameter:1.0,padDiameter:2.2,note:"Mains/snubber K73 film capacitor with high-voltage spacing."},

  VD1: {name:"FD320_THT_11x11mm_P1.50mm",mounting:"THT",width:11.0,height:11.0,padOffsets:[{x:-0.75,y:0},{x:0.75,y:0}],holeDiameter:0.8,padDiameter:1.8,note:"FD320 body about 11 x 11 x 9.5 mm, lead spacing 1.5 mm."},
  VD2: {name:"D_Axial_KD8_P10.16mm",mounting:"THT",width:8.0,height:3.5,padOffsets:[{x:-5.08,y:0},{x:5.08,y:0}],holeDiameter:0.9,padDiameter:1.9,note:"KS512A, through-hole KD-8 style."},
  VD3: {name:"D_Axial_KD4B_L4.8mm_D3.0mm_P10.16mm",mounting:"THT",width:10.16,height:3.2,padOffsets:[{x:-5.08,y:0},{x:5.08,y:0}],holeDiameter:1.0,padDiameter:2.0,note:"KD243Zh axial KD-4B."},
  VD4: {name:"D_Axial_KD4B_L4.8mm_D3.0mm_P10.16mm",mounting:"THT",width:10.16,height:3.2,padOffsets:[{x:-5.08,y:0},{x:5.08,y:0}],holeDiameter:1.0,padDiameter:2.0,note:"KD243Zh axial KD-4B."},
  VD5: {name:"D_Axial_KD4B_L4.8mm_D3.0mm_P10.16mm",mounting:"THT",width:10.16,height:3.2,padOffsets:[{x:-5.08,y:0},{x:5.08,y:0}],holeDiameter:1.0,padDiameter:2.0,note:"KD243Zh axial KD-4B."},
  HL1: {name:"LED_Rectangular_5.0x2.5mm_P2.54mm",mounting:"THT",width:5.0,height:2.5,padOffsets:[{x:-1.27,y:0},{x:1.27,y:0}],holeDiameter:0.8,padDiameter:1.8,note:"Kingbright L383SRWT rectangular 2.5 x 5 mm THT LED."},
  RU1: {name:"Varistor_FNR20_D24mm_P10.0mm",mounting:"THT",width:24.0,height:9.0,padOffsets:[{x:-5.0,y:0},{x:5.0,y:0}],holeDiameter:1.3,padDiameter:2.6,note:"FNR-20K391, 20 mm class disc; datasheet envelope approx. 24 x 28 x 9 mm, 10 mm lead spacing."},
  VD6: {name:"Bridge_RB15_D9.1mm_4P_P5.08mm",mounting:"THT",width:9.1,height:9.1,padOffsets:[{x:-2.54,y:-2.54},{x:-2.54,y:2.54},{x:2.54,y:-2.54},{x:2.54,y:2.54}],holeDiameter:1.0,padDiameter:2.0,note:"RB154 bridge, RB-15 / 4-circular through-hole package."},

  VT1: {name:"TO-92_Inline_P2.54mm",mounting:"THT",width:5.0,height:4.5,padOffsets:[{x:-2.54,y:0},{x:0,y:0},{x:2.54,y:0}],holeDiameter:0.8,padDiameter:1.8,note:"KP501A uses KT-26, equivalent to TO-92."},
  VT2: {name:"TO-92_Inline_P2.54mm",mounting:"THT",width:5.0,height:4.5,padOffsets:[{x:-2.54,y:0},{x:0,y:0},{x:2.54,y:0}],holeDiameter:0.8,padDiameter:1.8,note:"KP501A uses KT-26, equivalent to TO-92."},
  VT3: {name:"TO-220-3_Vertical_P2.54mm_KP707B1",mounting:"THT",width:10.0,height:4.8,padOffsets:[{x:-2.54,y:0},{x:0,y:0},{x:2.54,y:0}],holeDiameter:1.1,padDiameter:2.3,note:"Uses permitted KP707-series replacement in KT-28 / TO-220 plastic package."},

  VS1: {name:"T123-250_EXTERNAL_IF_3P_P5.08mm",mounting:"EXTERNAL",width:18.0,height:10.0,padOffsets:[{x:-5.08,y:0},{x:0,y:0},{x:5.08,y:0}],holeDiameter:1.5,padDiameter:3.0,note:"T123-250 is chassis-mounted high-current hardware (body up to ~42 mm); PCB footprint is an external A/K/G interface, not a fake solder footprint."},
  VS2: {name:"T123-250_EXTERNAL_IF_3P_P5.08mm",mounting:"EXTERNAL",width:18.0,height:10.0,padOffsets:[{x:-5.08,y:0},{x:0,y:0},{x:5.08,y:0}],holeDiameter:1.5,padDiameter:3.0,note:"T123-250 is chassis-mounted high-current hardware; PCB footprint is an external A/K/G interface."},

  FU1: {name:"Fuse_10x38mm_THT_Clips_P45.0mm_32A",mounting:"THT",width:50.0,height:12.0,padOffsets:[{x:-22.5,y:0},{x:22.5,y:0}],holeDiameter:1.5,padDiameter:3.2,note:"32 A mains fuse represented by a 10 x 38 mm cartridge with PCB clips; not a 5 x 20 mm low-current holder."},
  FU2: {name:"Fuse_10x38mm_THT_Clips_P45.0mm_32A",mounting:"THT",width:50.0,height:12.0,padOffsets:[{x:-22.5,y:0},{x:22.5,y:0}],holeDiameter:1.5,padDiameter:3.2,note:"32 A mains fuse represented by a 10 x 38 mm cartridge with PCB clips."},

  XP1: {name:"Phoenix_MSTBA_2,5_5-G-5.08_1x05_P5.08mm",mounting:"THT",width:26.0,height:10.0,padOffsets:[{x:-10.16,y:0},{x:-5.08,y:0},{x:0,y:0},{x:5.08,y:0},{x:10.16,y:0}],holeDiameter:1.3,padDiameter:2.8,note:"Real 5-position 5.08 mm board connector used as CAD/layout substitute for legacy MRN-5Sh; exact MRN mechanical drawing must be substituted if original connector is mandatory."},
}

const pcbPlacement: Record<string,{x:number;y:number}> = {
  R1:{x:-62,y:39}, R2:{x:-53,y:39}, VD1:{x:-42,y:39}, C1:{x:-28,y:39}, C2:{x:-17,y:39}, VD2:{x:-4,y:39},
  VT1:{x:10,y:39}, R3:{x:20,y:39}, R4:{x:29,y:39}, VT2:{x:39,y:39}, R5:{x:49,y:39}, VT3:{x:61,y:39},
  R6:{x:-62,y:24}, R7:{x:-51,y:24}, VD3:{x:-37,y:24}, HL1:{x:-23,y:24}, RU1:{x:-5,y:24}, VD6:{x:17,y:24},
  R8:{x:31,y:24}, VD4:{x:43,y:24}, VS1:{x:58,y:24},
  R9:{x:-62,y:8}, VD5:{x:-49,y:8}, VS2:{x:-33,y:8}, C3:{x:-10,y:8}, XP1:{x:20,y:8},
  FU1:{x:-36,y:-30}, FU2:{x:27,y:-30},
}

for (const c of components) {
  c.schX = c.schX * 4 / 3
  const fp=footprints[c.ref]
  const pos=pcbPlacement[c.ref]
  if(!fp || !pos) throw new Error("Missing footprint or placement for " + c.ref)
  c.pcbX=pos.x
  c.pcbY=pos.y
  c.through=fp.mounting !== "SMD"
  c.pcbW=fp.width
  c.pcbH=fp.height
}

const elements: any[] = [
  {type:"pcb_board", pcb_board_id:"pcb_board_0", center:{x:0,y:0}, width:140, height:100},
  {type:"schematic_text", schematic_text_id:"title", position:{x:-28,y:15}, text:"7330744 Variant 6 - Photo Relay", font_size:0.65},
  {type:"schematic_text", schematic_text_id:"note1", position:{x:-28,y:14}, text:"Educational Altium reconstruction from the verified Multisim topology.", font_size:0.35},
  {type:"schematic_text", schematic_text_id:"note2", position:{x:-28,y:-15}, text:"Power stage is an educational equivalent. Not fabrication-ready for 220 V / tens of kW.", font_size:0.30},
  {type:"schematic_text", schematic_text_id:"note3", position:{x:-28,y:-16}, text:"XP1.5 CASE/SERVICE assignment requires verification against the original assembly.", font_size:0.30},
]

const netPorts = new Map<string,string[]>()
const netNames = new Set<string>()
for (const c of components) for (const p of c.pins) netNames.add(p.net)
for (const net of [...netNames]) {
  elements.push({type:"source_net", source_net_id:`net_${net}`, name:net})
}

function pinGeometry(count:number, index:number) {
  if (count === 2) return index === 0 ? {side:"left",y:0} : {side:"right",y:0}
  if (count === 3) {
    if (index === 0) return {side:"left",y:0.38}
    if (index === 1) return {side:"right",y:0.38}
    return {side:"left",y:-0.38}
  }
  if (count === 4) {
    if (index === 0) return {side:"left",y:0.40}
    if (index === 1) return {side:"left",y:-0.40}
    if (index === 2) return {side:"right",y:0.40}
    return {side:"right",y:-0.40}
  }
  const offsets=[0.8,0.4,0,-0.4,-0.8]
  return {side:"left",y:offsets[index] ?? 0}
}

function pcbPadPosition(c:ComponentSpec, index:number) {
  const fp=footprints[c.ref]
  const offset=fp.padOffsets[index]
  if(!offset) throw new Error("Missing pad offset for " + c.ref + " pin " + (index+1))
  return {x:c.pcbX+offset.x, y:c.pcbY+offset.y}
}

for (const c of components) {
  const scid=`sc_${c.ref}`
  const schcid=`sch_${c.ref}`
  const pcid=`pcb_${c.ref}`
  const compHeight=c.pins.length >= 5 ? 2.4 : c.pins.length >= 3 ? 1.6 : 1.2
  elements.push({type:"source_component",source_component_id:scid,name:c.ref})
  elements.push({
    type:"schematic_component",
    schematic_component_id:schcid,
    source_component_id:scid,
    center:{x:c.schX,y:c.schY},
    size:{width:2,height:compHeight},
    symbol_display_value:c.value,
  })
  elements.push({
    type:"pcb_component",
    pcb_component_id:pcid,
    source_component_id:scid,
    center:{x:c.pcbX,y:c.pcbY},
    width:c.pcbW ?? Math.max(3.5,c.pins.length*2.2),
    height:c.pcbH ?? 3.2,
    layer:"top",
    rotation:0,
  })
  elements.push({
    type:"pcb_silkscreen_rect",
    pcb_silkscreen_rect_id:`silk_${c.ref}`,
    pcb_component_id:pcid,
    center:{x:c.pcbX,y:c.pcbY},
    width:c.pcbW ?? Math.max(3.5,c.pins.length*2.2),
    height:c.pcbH ?? 3.2,
    stroke_width:0.16,
    is_filled:false,
    has_stroke:true,
    layer:"top",
    ccw_rotation:0,
  })

  for (const [pi,pin] of c.pins.entries()) {
    const spid=`sp_${c.ref}_${pi+1}`
    const schpid=`schp_${c.ref}_${pi+1}`
    const ppid=`pp_${c.ref}_${pi+1}`
    const g=pinGeometry(c.pins.length,pi)
    const terminalX=c.schX+(g.side==="left"?-1.5:1.5)
    const terminalY=c.schY+g.y
    const endpointX=terminalX+(g.side==="left"?-1.1:1.1)
    const labelX=endpointX+(g.side==="left"?-0.35:0.35)

    elements.push({
      type:"source_port",source_port_id:spid,source_component_id:scid,
      pin_number:pi+1,name:pin.name,port_hints:[pin.name,`pin${pi+1}`,`${pi+1}`],
    })
    elements.push({
      type:"schematic_port",schematic_port_id:schpid,schematic_component_id:schcid,
      source_port_id:spid,center:{x:terminalX,y:terminalY},
      distance_from_component_edge:0.5,facing_direction:g.side,
      display_pin_label:pin.name,
    })
    elements.push({
      type:"schematic_trace",schematic_trace_id:`scht_${c.ref}_${pi+1}`,
      source_trace_id:`trace_${pin.net}`,
      edges:[{from:{x:terminalX,y:terminalY},to:{x:endpointX,y:terminalY}}],
      junctions:[],
    })
    elements.push({
      type:"schematic_net_label",schematic_net_label_id:`label_${c.ref}_${pi+1}`,
      source_net_id:`net_${pin.net}`,text:pin.net,
      center:{x:labelX,y:terminalY},anchor_position:{x:endpointX,y:terminalY},
      anchor_side:g.side==="left"?"right":"left",
    })
    elements.push({
      type:"pcb_port",pcb_port_id:ppid,source_port_id:spid,pcb_component_id:pcid,
    })
    const pp=pcbPadPosition(c,pi)
    const fp=footprints[c.ref]
    if (fp.mounting !== "SMD") {
      elements.push({
        type:"pcb_plated_hole",pcb_plated_hole_id:`pth_${c.ref}_${pi+1}`,
        pcb_component_id:pcid,pcb_port_id:ppid,shape:"circle",
        x:pp.x,y:pp.y,
        outer_diameter:fp.padDiameter ?? 2.0,
        hole_diameter:fp.holeDiameter ?? 0.9,
        ccw_rotation:0,
      })
    } else {
      elements.push({
        type:"pcb_smtpad",pcb_smtpad_id:`smd_${c.ref}_${pi+1}`,
        pcb_component_id:pcid,pcb_port_id:ppid,shape:"rect",
        x:pp.x,y:pp.y,
        width:fp.smdPad?.width ?? 1.5,
        height:fp.smdPad?.height ?? 1.0,
        layer:"top",ccw_rotation:0,
      })
    }
    const arr=netPorts.get(pin.net) ?? []
    arr.push(spid)
    netPorts.set(pin.net,arr)
  }
}

for (const [net,ports] of netPorts.entries()) {
  elements.push({
    type:"source_trace",
    source_trace_id:`trace_${net}`,
    connected_source_port_ids:ports,
    connected_source_net_ids:[`net_${net}`],
    name:net,
  })
}

for (const [i,point] of [[-66,-46],[66,-46],[-66,46],[66,46]].entries()) {
  const [x,y]=point as number[]
  elements.push({
    type:"pcb_hole",pcb_hole_id:`mh_${i+1}`,x,y,hole_diameter:3.2,
  })
}

const outDir=process.argv[2] ?? "out"
await mkdir(outDir,{recursive:true})
await Bun.write(`${outDir}/PhotoRelay_V6.circuit.json`,JSON.stringify(elements,null,2))

const converter=new CircuitJsonToAltiumConverter(elements,{
  projectName:"PhotoRelay_V6",
  schematicUnitsPerCircuitUnit:20,
  schematicSheets:[{width:64,height:36,circuitOrigin:{x:32,y:18}}],
  schematicProjectContext:{
    projectName:"7330744_Variant6_PhotoRelay",
    documentName:"PhotoRelay_V6.SchDoc",
  },
})
converter.runUntilFinished()
const output=converter.getOutput()
if(output.schematics.length!==1) throw new Error(`Expected one schematic, got ${output.schematics.length}`)
const schematic=output.schematics[0]!

const footprintNameByRef=new Map(Object.entries(footprints).map(([ref,fp])=>[ref,fp.name]))
const pcbAsciiWithFootprints=output.pcb.asciiContent
  .split(/\r?\n/)
  .map((line)=>{
    if(!line.startsWith("|RECORD=Component|")) return line
    const match=/\|SOURCEDESIGNATOR=([^|]+)/.exec(line)
    if(!match) return line
    const ref=match[1]!
    const footprint=footprintNameByRef.get(ref)
    if(!footprint) throw new Error("No Stage 8 footprint for " + ref)
    return line.replace(/\|PATTERN=[^|]*/,"|PATTERN="+footprint)
  })
  .join("\r\n")
const pcbContent=serializeAltiumPcbDocWithKeepoutRules(pcbAsciiWithFootprints)

const pcbParsed=parseAltiumBinaryPcbDoc(pcbContent)
const schParsed=parseAltiumSchDoc(schematic.content)
const pcbValidation=validateAltiumDocument(pcbParsed,{profile:"strict"})
const schValidation=validateAltiumDocument(schParsed,{profile:"strict"})
const dangling=getDanglingPcbReferences(pcbParsed)

let projectContent=output.project.content
  .replace("ProjectName=PhotoRelay_V6","ProjectName=7330744_Variant6_PhotoRelay")
const projectParsed=parseAltiumPrjPcb(projectContent)

const assignedPatterns=pcbParsed.components.map((component:any)=>({
  reference:component.getDecoded("SOURCEDESIGNATOR") ?? component.get("SOURCEDESIGNATOR"),
  pattern:component.getDecoded("PATTERN") ?? component.get("PATTERN"),
}))
const badPatterns=assignedPatterns.filter(({reference,pattern}:any)=>footprintNameByRef.get(reference)!==pattern)

const validation={
  stage:8,
  generator:"circuit-json-to-altium pinned a399f6a + altiumts 0.0.95",
  project_filename:"7330744_Variant6_PhotoRelay.PrjPcb",
  schematic_filename:schematic.filename,
  pcb_filename:output.pcb.filename,
  board_size_mm:{width:140,height:100},
  component_specs:components.length,
  source_nets:netNames.size,
  source_ports:components.reduce((n,c)=>n+c.pins.length,0),
  schematic_components:schParsed.components.length,
  schematic_pins:schParsed.pins.length,
  pcb_components:pcbParsed.components.length,
  pcb_pads:pcbParsed.getRecordsByKind("Pad").length,
  pcb_nets:pcbParsed.nets.length,
  project_documents:projectParsed.documents.map((d:any)=>d.path),
  assigned_patterns:assignedPatterns,
  all_patterns_match:badPatterns.length===0,
  schematic_strict_valid:schValidation.valid,
  pcb_strict_valid:pcbValidation.valid,
  pcb_dangling_references:dangling,
}
if(!schValidation.valid) throw new Error("Schematic strict validation failed: "+JSON.stringify(schValidation))
if(!pcbValidation.valid) throw new Error("PCB strict validation failed: "+JSON.stringify(pcbValidation))
if(dangling.length) throw new Error("Dangling PCB references: "+JSON.stringify(dangling))
if(badPatterns.length) throw new Error("Footprint PATTERN mismatch: "+JSON.stringify(badPatterns))
if(schParsed.components.length!==components.length) throw new Error("Schematic component count mismatch")
if(pcbParsed.components.length!==components.length) throw new Error("PCB component count mismatch")

const csvCell=(value:any)=>{
  const s=String(value ?? "")
  return `"${s.replaceAll('"','""')}"`
}
const footprintRows=components.map((component)=>{
  const fp=footprints[component.ref]
  return [component.ref,component.value,fp.mounting,fp.name,fp.width,fp.height,fp.note].map(csvCell).join(",")
})
const footprintCsv=[
  ["Reference","Value","Mounting","Footprint","Width_mm","Height_mm","Engineering_note"].map(csvCell).join(","),
  ...footprintRows,
].join("\r\n")

const footprintMd=[
  "# Этап 8. Назначение реальных корпусов",
  "",
  "Проект: заказ 7330744, вариант 6, фотореле.",
  "",
  "Принцип выбора: SMD применяется там, где это не ухудшает электрическую правдоподобность. Силовые, оптические, высоковольтные и механические элементы оставлены THT или вынесены во внешний монтаж.",
  "",
  "## Ключевые решения",
  "",
  "- R1 - 1206; R2/R3/R4/R5 - 0805; R6/R8/R9 - 1206; R7 - 2512 HV.",
  "- C1 К50-35 - радиальный электролит D5 P2; C2 К73 - пленочный THT P5; C3 К73 в сетевой цепи - пленочный HV P15.",
  "- VD1 ФД320 - собственный THT-корпус около 11 x 11 мм с шагом выводов 1.5 мм.",
  "- VD2 КС512А - THT KD-8; VD3/VD4/VD5 КД243Ж - осевой KD-4B, посадка P10.16.",
  "- HL1 L383SRWT - прямоугольный THT LED 5.0 x 2.5 мм, P2.54.",
  "- VD6 RB154 - RB-15, круглый 4-выводный THT около 9.1 x 9.1 мм.",
  "- VT1/VT2 КП501А - КТ-26 / TO-92, P2.54.",
  "- VT3 - разрешенная замена КП707Б1 в КТ-28 / TO-220-3.",
  "- RU1 FNR-20K391 - дисковый варистор класса 20 мм, корпус около 24 x 28 x 9 мм, P10.",
  "- FU1/FU2 - 32 A: корпус 10 x 38 мм с THT-клипсами, P45; малый 5 x 20 мм не используется.",
  "- VS1/VS2 T123-250 - внешний силовой монтаж. На PCB оставлен 3-контактный интерфейс A/K/G; сам тиристор не изображается как ложный паяемый корпус.",
  "- XP1 - реальный 5-позиционный THT-коннектор Phoenix MSTBA 2,5/5-G-5,08 как CAD/layout-замена старого МРН-5Ш. При обязательном применении именно МРН-5Ш его точный механический чертеж нужно подставить перед производством.",
  "",
  "## Проверка",
  "",
  `В PcbDoc назначено ${assignedPatterns.length} PATTERN-полей. Несовпадений: ${badPatterns.length}.`,
  `Strict validation SchDoc: ${schValidation.valid ? "PASS" : "FAIL"}.`,
  `Strict validation PcbDoc: ${pcbValidation.valid ? "PASS" : "FAIL"}.`,
  `Dangling PCB references: ${dangling.length}.`,
  "",
  "Плата на этом этапе увеличена до 140 x 100 мм, чтобы крупные THT-компоненты и держатели предохранителей не пересекались. Трассировка остается следующим этапом.",
].join("\r\n")

await Bun.write(`${outDir}/PhotoRelay_V6.SchDoc`,schematic.content)
await Bun.write(`${outDir}/PhotoRelay_V6.PcbDoc`,pcbContent)
await Bun.write(`${outDir}/7330744_Variant6_PhotoRelay.PrjPcb`,projectContent)
await Bun.write(`${outDir}/PhotoRelay_V6.circuit.json`,JSON.stringify(elements,null,2))
await Bun.write(`${outDir}/7330744_Stage8_Validation.json`,JSON.stringify(validation,null,2))
await Bun.write(`${outDir}/7330744_Этап8_Корпуса.csv`,footprintCsv)
await Bun.write(`${outDir}/7330744_Этап8_Корпуса.md`,footprintMd)

const readme=[
  "7330744 Variant 6 - Photo Relay - Stage 8 real footprints",
  "",
  "Native Altium files:",
  "- 7330744_Variant6_PhotoRelay.PrjPcb",
  "- PhotoRelay_V6.SchDoc",
  "- PhotoRelay_V6.PcbDoc",
  "",
  "Stage 8 assigns realistic footprint names and pad geometry to all 28 PCB components.",
  "SMD is preferred for suitable low-power resistors. Legacy/high-voltage/power parts remain THT or external.",
  "T123-250 devices are chassis-mounted and represented by external A/K/G interfaces.",
  "XP1 uses a real 5.08 mm Phoenix board connector as a CAD substitute because a reliable MRN-5Sh mechanical drawing was not available.",
  "Routing is not part of Stage 8.",
].join("\r\n")
await Bun.write(`${outDir}/README_STAGE8.txt`,readme)

function sha256(data:Uint8Array|string){
  return createHash("sha256").update(data).digest("hex")
}
const manifest={
  "7330744_Variant6_PhotoRelay.PrjPcb":sha256(projectContent),
  "PhotoRelay_V6.SchDoc":sha256(schematic.content),
  "PhotoRelay_V6.PcbDoc":sha256(pcbContent),
}
await Bun.write(`${outDir}/SHA256SUMS.json`,JSON.stringify(manifest,null,2))

const zip=new JSZip()
zip.file("7330744_Variant6_PhotoRelay.PrjPcb",projectContent)
zip.file("PhotoRelay_V6.SchDoc",schematic.content)
zip.file("PhotoRelay_V6.PcbDoc",pcbContent)
zip.file("PhotoRelay_V6.circuit.json",JSON.stringify(elements,null,2))
zip.file("7330744_Stage8_Validation.json",JSON.stringify(validation,null,2))
zip.file("7330744_Этап8_Корпуса.csv",footprintCsv)
zip.file("7330744_Этап8_Корпуса.md",footprintMd)
zip.file("README_STAGE8.txt",readme)
zip.file("SHA256SUMS.json",JSON.stringify(manifest,null,2))
await Bun.write(`${outDir}/7330744_Этап8_Реальные_корпуса_Altium.zip`,await zip.generateAsync({type:"uint8array",compression:"DEFLATE"}))

console.log(JSON.stringify(validation,null,2))
