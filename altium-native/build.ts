import { CircuitJsonToAltiumConverter } from "circuit-json-to-altium"
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

const elements: any[] = [
  {type:"pcb_board", pcb_board_id:"pcb_board_0", center:{x:0,y:0}, width:100, height:70},
  {type:"schematic_text", schematic_text_id:"title", position:{x:-22,y:15}, text:"7330744 Variant 6 - Photo Relay", font_size:0.65},
  {type:"schematic_text", schematic_text_id:"note1", position:{x:-22,y:14}, text:"Educational Altium reconstruction from the verified Multisim topology.", font_size:0.35},
  {type:"schematic_text", schematic_text_id:"note2", position:{x:-22,y:-15}, text:"Power stage is an educational equivalent. Not fabrication-ready for 220 V / tens of kW.", font_size:0.30},
  {type:"schematic_text", schematic_text_id:"note3", position:{x:-22,y:-16}, text:"XP1.5 CASE/SERVICE assignment requires verification against the original assembly.", font_size:0.30},
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
  const n=c.pins.length
  const pitch=n >= 4 ? 1.8 : 2.2
  const total=(n-1)*pitch
  return {x:c.pcbX-total/2+index*pitch, y:c.pcbY}
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
    if (c.through) {
      elements.push({
        type:"pcb_plated_hole",pcb_plated_hole_id:`pth_${c.ref}_${pi+1}`,
        pcb_component_id:pcid,pcb_port_id:ppid,shape:"circle",
        x:pp.x,y:pp.y,outer_diameter:1.8,hole_diameter:0.9,ccw_rotation:0,
      })
    } else {
      elements.push({
        type:"pcb_smtpad",pcb_smtpad_id:`smd_${c.ref}_${pi+1}`,
        pcb_component_id:pcid,pcb_port_id:ppid,shape:"rect",
        x:pp.x,y:pp.y,width:1.5,height:1.0,layer:"top",ccw_rotation:0,
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

for (const [i,point] of [[-46,-31],[46,-31],[-46,31],[46,31]].entries()) {
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
  schematicSheets:[{width:50,height:34,circuitOrigin:{x:25,y:17}}],
  schematicProjectContext:{
    projectName:"7330744_Variant6_PhotoRelay",
    documentName:"PhotoRelay_V6.SchDoc",
  },
})
converter.runUntilFinished()
const output=converter.getOutput()
if(output.schematics.length!==1) throw new Error(`Expected one schematic, got ${output.schematics.length}`)
const schematic=output.schematics[0]!

const pcbParsed=parseAltiumBinaryPcbDoc(output.pcb.content)
const schParsed=parseAltiumSchDoc(schematic.content)
const pcbValidation=validateAltiumDocument(pcbParsed,{profile:"strict"})
const schValidation=validateAltiumDocument(schParsed,{profile:"strict"})
const dangling=getDanglingPcbReferences(pcbParsed)

let projectContent=output.project.content
  .replace("ProjectName=PhotoRelay_V6","ProjectName=7330744_Variant6_PhotoRelay")
const projectParsed=parseAltiumPrjPcb(projectContent)

const validation={
  generator:"circuit-json-to-altium 0.0.1 + altiumts 0.0.95",
  project_filename:"7330744_Variant6_PhotoRelay.PrjPcb",
  schematic_filename:schematic.filename,
  pcb_filename:output.pcb.filename,
  component_specs:components.length,
  source_nets:netNames.size,
  source_ports:components.reduce((n,c)=>n+c.pins.length,0),
  schematic_components:schParsed.components.length,
  schematic_pins:schParsed.pins.length,
  schematic_wires:schParsed.wires.length,
  schematic_net_labels:schParsed.netLabels.length,
  pcb_components:pcbParsed.components.length,
  pcb_pads:pcbParsed.getRecordsByKind("Pad").length,
  pcb_nets:pcbParsed.nets.length,
  project_documents:projectParsed.documents.map((d:any)=>d.path),
  schematic_strict_valid:schValidation.valid,
  pcb_strict_valid:pcbValidation.valid,
  pcb_dangling_references:dangling,
}
if(!schValidation.valid) throw new Error("Schematic strict validation failed: "+JSON.stringify(schValidation))
if(!pcbValidation.valid) throw new Error("PCB strict validation failed: "+JSON.stringify(pcbValidation))
if(dangling.length) throw new Error("Dangling PCB references: "+JSON.stringify(dangling))
if(schParsed.components.length!==components.length) throw new Error("Schematic component count mismatch")
if(pcbParsed.components.length!==components.length) throw new Error("PCB component count mismatch")

await Bun.write(`${outDir}/PhotoRelay_V6.SchDoc`,schematic.content)
await Bun.write(`${outDir}/PhotoRelay_V6.PcbDoc`,output.pcb.content)
await Bun.write(`${outDir}/7330744_Variant6_PhotoRelay.PrjPcb`,projectContent)
await Bun.write(`${outDir}/7330744_Stage7_Validation.json`,JSON.stringify(validation,null,2))

const readme=[
  "7330744 Variant 6 - Photo Relay - Altium Designer project",
  "",
  "Files:",
  "- 7330744_Variant6_PhotoRelay.PrjPcb",
  "- PhotoRelay_V6.SchDoc",
  "- PhotoRelay_V6.PcbDoc",
  "- PhotoRelay_V6.circuit.json",
  "- 7330744_Stage7_Validation.json",
  "",
  "The SchDoc and PcbDoc are native Altium binary compound documents.",
  "They were generated from Circuit JSON and parsed back with altiumts.",
  "Strict structural validation passed for both documents.",
  "The PCB is a two-layer project foundation with component placement and net-assigned pads.",
  "Routing is intentionally deferred to the next PCB-layout stage.",
  "The power stage is educational only and is not certified for fabrication at 220 V / tens of kW.",
  "XP1 pin 5 CASE/SERVICE remains a topology assumption requiring verification against the original assembly.",
].join("\r\n")
await Bun.write(`${outDir}/README_STAGE7.txt`,readme)

function sha256(data:Uint8Array|string){
  return createHash("sha256").update(data).digest("hex")
}
const manifest={
  "7330744_Variant6_PhotoRelay.PrjPcb":sha256(projectContent),
  "PhotoRelay_V6.SchDoc":sha256(schematic.content),
  "PhotoRelay_V6.PcbDoc":sha256(output.pcb.content),
}
await Bun.write(`${outDir}/SHA256SUMS.json`,JSON.stringify(manifest,null,2))

const zip=new JSZip()
zip.file("7330744_Variant6_PhotoRelay.PrjPcb",projectContent)
zip.file("PhotoRelay_V6.SchDoc",schematic.content)
zip.file("PhotoRelay_V6.PcbDoc",output.pcb.content)
zip.file("PhotoRelay_V6.circuit.json",JSON.stringify(elements,null,2))
zip.file("7330744_Stage7_Validation.json",JSON.stringify(validation,null,2))
zip.file("README_STAGE7.txt",readme)
zip.file("SHA256SUMS.json",JSON.stringify(manifest,null,2))
await Bun.write(`${outDir}/7330744_Этап7_Altium_Project.zip`,await zip.generateAsync({type:"uint8array",compression:"DEFLATE"}))

console.log(JSON.stringify(validation,null,2))
