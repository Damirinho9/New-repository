import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { dirname, join, resolve } from 'node:path';
const require = createRequire(import.meta.url);
const CFB = require('cfb');

const input=resolve(process.argv[2]||'stage11/pinmap-out/PhotoRelay_V6.PcbDoc');
const output=resolve(process.argv[3]||input);
const bytes=readFileSync(input);
const container=CFB.read(bytes,{type:'buffer'});
const sha=(b)=>createHash('sha256').update(b).digest('hex');
const oldStreams=new Map(container.FileIndex.map((entry,i)=>[container.FullPaths[i],Buffer.from(entry.content||[])]).filter(([name,data])=>data.length));
const mains="InNet('L') OR InNet('N') OR InNet('SW') OR InNet('BR_A')";
const sensitive="InNet('SENS')";
const rules=[];
function add(kind,ruleKind,name,priority,scope1,scope2,parameters,netScope='AnyNet'){
 const fields={
  SELECTION:'FALSE',LAYER:'TOP',LOCKED:'FALSE',POLYGONOUTLINE:'FALSE',USERROUTED:'TRUE',UNIONINDEX:'0',
  RULEKIND:ruleKind,NETSCOPE:netScope,LAYERKIND:'SameLayer',SCOPE1EXPRESSION:scope1,SCOPE2EXPRESSION:scope2,
  NAME:name,ENABLED:'TRUE',PRIORITY:String(priority),COMMENT:'',
  UNIQUEID:sha(Buffer.from('7330744:'+name)).slice(0,8).toUpperCase(),DEFINEDBYLOGICALDOCUMENT:'FALSE',...parameters
 };
 const text='|'+Object.entries(fields).map(([key,value])=>key+'='+value).join('|')+'\0';
 const payload=Buffer.from(text,'latin1');
 const frame=Buffer.alloc(payload.length+6);frame.writeUInt16LE(kind,0);frame.writeUInt32LE(payload.length,2);payload.copy(frame,6);
 rules.push({kind,ruleKind,name,priority,scope1,scope2,parameters,fields,frame});
}
// Native UInt16 kinds and property spellings are verified against a real Altium PcbDoc
// in KiCad's QA corpus. These are new project constraints, not copied project-specific scopes.
add(0,'Clearance','Clearance_Mains',1,mains,'All',{GAP:'3mm'},'DifferentNets');
add(0,'Clearance','Clearance_Sensitive',2,sensitive,'All',{GAP:'0.3mm'},'DifferentNets');
add(0,'Clearance','Clearance_Default',3,'All','All',{GAP:'0.3mm'},'DifferentNets');
add(2,'Width','Width_Sensitive',1,sensitive,'All',{MINLIMIT:'0.35mm',MAXLIMIT:'0.35mm',PREFEREDWIDTH:'0.35mm'});
add(2,'Width','Width_Default',2,'All','All',{MINLIMIT:'0.35mm',MAXLIMIT:'2mm',PREFEREDWIDTH:'0.5mm'});
add(15,'ShortCircuit','ShortCircuit',1,'All','All',{ALLOWED:'FALSE'});
add(16,'UnRoutedNet','UnRoutedNet',1,'All','All',{});
add(42,'HoleSize','HoleSize',1,'All','All',{ABSOLUTEVALUES:'TRUE',MAXLIMIT:'3.2mm',MINLIMIT:'0.3mm',MAXPERCENT:'80.000',MINPERCENT:'20.000'});
add(24,'ComponentClearance','ComponentClearance',1,'All','All',{GAP:'0.3mm',VERTICALGAP:'0.3mm',COLLISIONCHECKMODE:'3',SHOWDISTANCES:'FALSE'});
add(54,'SilkToSolderMaskClearance','SilkToSolderMask',1,'All','All',{MINSILKSCREENTOMASKGAP:'0.15mm',CLEARANCETOEXPOSEDCOPPER:'FALSE'});
add(11,'RoutingVias','RoutingVias',1,'All','All',{HOLEWIDTH:'0.4mm',WIDTH:'0.9mm',VIASTYLE:'Through Hole',MINHOLEWIDTH:'0.4mm',MAXHOLEWIDTH:'0.4mm',MINWIDTH:'0.9mm',MAXWIDTH:'0.9mm'});

const header=Buffer.alloc(4);header.writeUInt32LE(rules.length);
CFB.utils.cfb_add(container,'Rules6/Header',header);
CFB.utils.cfb_add(container,'Rules6/Data',Buffer.concat(rules.map(r=>r.frame)));
const result=CFB.write(container,{type:'buffer'});
writeFileSync(output,result);
const reopened=CFB.read(result,{type:'buffer'});
for(const [name,data] of oldStreams){
 if(name.endsWith('/Rules6/Data')||name.endsWith('/Rules6/Header'))continue;
 const index=reopened.FullPaths.indexOf(name);
 if(index<0||!Buffer.from(reopened.FileIndex[index].content||[]).equals(data))throw Error('Non-rule stream changed: '+name);
}
const get=(name)=>{
 const i=reopened.FullPaths.findIndex(x=>x.endsWith('/'+name));
 if(i<0)throw Error('Missing stream '+name);
 return Buffer.from(reopened.FileIndex[i].content);
};
const savedData=get('Rules6/Data');let offset=0;const saved=[];
while(offset<savedData.length){
 const kind=savedData.readUInt16LE(offset),length=savedData.readUInt32LE(offset+2);offset+=6;
 const text=savedData.subarray(offset,offset+length).toString('latin1').replace(/\0$/,'');offset+=length;
 const fields=Object.fromEntries(text.split('|').filter(x=>x.includes('=')).map(x=>{const i=x.indexOf('=');return [x.slice(0,i),x.slice(i+1)];}));
 saved.push({kind,...fields});
}
if(offset!==savedData.length||saved.length!==11||get('Rules6/Header').readUInt32LE(0)!==11)throw Error('Invalid Rules6 framing/count');
if(saved.some(r=>r.ENABLED!=='TRUE'))throw Error('A rule is disabled');
const summary={
 rules_count:saved.length,rules_types:[...new Set(saved.map(r=>r.RULEKIND))],
 all_rules_enabled:true,non_rule_stream_payloads_unchanged:true,
 original_sha256:sha(bytes),result_sha256:sha(result),
 native_altium_save_confirmed:false,native_altium_drc_performed:false,
 format_reference:{url:'https://github.com/KiCad/kicad-source-mirror/blob/master/qa/data/pcbnew/plugins/altium/eDP_adapter_dvt1_source/eDP_adapter_dvt1.PcbDoc',sha256:'17896fdfeaac33a84ac3063db063d0a4d211c127c997632c8000837c0ce6fc12'},
 rules:saved
};
writeFileSync(join(dirname(output),'7330744_Stage11_Rules.json'),JSON.stringify(summary,null,2));
const rows=['rule_name,rule_kind,native_kind,priority,scope1,scope2,parameters'];
for(const rule of rules)rows.push([rule.name,rule.ruleKind,rule.kind,rule.priority,rule.scope1,rule.scope2,JSON.stringify(rule.parameters)].map(x=>'"'+String(x).replaceAll('"','""')+'"').join(','));
writeFileSync(join(dirname(output),'7330744_Stage11_Rules.csv'),'\ufeff'+rows.join('\n')+'\n');
console.log(JSON.stringify({rules_count:summary.rules_count,rules_types:summary.rules_types,all_rules_enabled:true,non_rule_stream_payloads_unchanged:true,result_sha256:summary.result_sha256,native_altium_save_confirmed:false},null,2));
