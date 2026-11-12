import re, math, sys, hashlib, xml.etree.ElementTree as ET
from pathlib import Path

SRC=Path(sys.argv[1]).resolve()
OUT=Path(sys.argv[2]).resolve()
text=SRC.read_text(encoding="utf-8")

# Minimal S-expression parser for the intentionally simple KiCad file generated
# for this project. It preserves all pad/net/segment/via geometry exactly.
tokens=[];i=0
while i<len(text):
    c=text[i]
    if c.isspace(): i+=1; continue
    if c in "()": tokens.append(c); i+=1; continue
    if c=='"':
        j=i+1;s=""
        while j<len(text):
            if text[j]=="\\" and j+1<len(text): s+=text[j+1];j+=2
            elif text[j]=='"': break
            else:s+=text[j];j+=1
        tokens.append(("str",s));i=j+1;continue
    j=i
    while j<len(text) and not text[j].isspace() and text[j] not in "()":j+=1
    atom=text[i:j]
    try:
        v=int(atom) if re.fullmatch(r"[-+]?\d+",atom) else float(atom) if re.fullmatch(r"[-+]?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?",atom) else atom
    except:v=atom
    tokens.append(v);i=j
pos=0
def parse():
    global pos
    t=tokens[pos];pos+=1
    if t=="(":
        a=[]
        while tokens[pos]!=")":a.append(parse())
        pos+=1;return a
    if isinstance(t,tuple):return t[1]
    return t
root=parse()
def children(n,h):return [x for x in n[1:] if isinstance(x,list) and x and x[0]==h]
def child(n,h):
    x=children(n,h);return x[0] if x else None
def f(v):
    if isinstance(v,int):return str(v)
    s=("%.9f"%float(v)).rstrip("0").rstrip(".");return s or "0"

nets={int(n[1]):n[2] for n in children(root,"net")}

def fpinfo(fp):
    at=child(fp,"at");x=float(at[1]);y=float(at[2]);ang=float(at[3]) if len(at)>3 and isinstance(at[3],(int,float)) else 0.0
    ref=val=None
    for ft in children(fp,"fp_text"):
        if ft[1]=="reference":ref=ft[2]
        elif ft[1]=="value":val=ft[2]
    pads=[]
    for pd in children(fp,"pad"):
        pa=child(pd,"at");sz=child(pd,"size");dr=child(pd,"drill");nt=child(pd,"net")
        pads.append({
            "num":str(pd[1]),"type":pd[2],"shape":pd[3],
            "x":float(pa[1]),"y":float(pa[2]),
            "a":float(pa[3]) if len(pa)>3 and isinstance(pa[3],(int,float)) else 0.0,
            "sx":float(sz[1]),"sy":float(sz[2]),
            "drill":float(dr[1]) if dr and isinstance(dr[1],(int,float)) else None,
            "net":int(nt[1]) if nt else -1})
    return {"name":fp[1],"ref":ref,"val":val,"x":x,"y":y,"a":ang,"pads":pads}

infos=[fpinfo(x) for x in children(root,"footprint")]
m=1
for z in infos:
    if not z["ref"]:z["ref"]=f"MH{m}";z["val"]="Mounting hole 3.2mm";m+=1

def seginfo(s):
    a=child(s,"start");b=child(s,"end")
    return float(a[1]),float(a[2]),float(b[1]),float(b[2]),float(child(s,"width")[1]),child(s,"layer")[1],int(child(s,"net")[1])
def viainfo(v):
    a=child(v,"at");return float(a[1]),float(a[2]),float(child(v,"size")[1]),float(child(v,"drill")[1]),int(child(v,"net")[1])
segs=children(root,"segment");vias=children(root,"via")

R=ET.Element("Source",{"Type":"DipTrace-PCB","Version":"5.3.0.3","Units":"mm"})
co=ET.SubElement(R,"Library",{"Type":"DipTrace-ComponentLibrary","Version":"5.3.0.3","Units":"mm"})
L=ET.SubElement(co,"Library",{"Type":"DipTrace-PatternLibrary","Version":"5.3.0.3","Units":"mm"})
PSS=ET.SubElement(L,"PadStyles");PATS=ET.SubElement(L,"Patterns")
styles={}
def style(pd):
    k=(pd["type"],round(pd["sx"],6),round(pd["sy"],6),None if pd["drill"] is None else round(pd["drill"],6),pd["shape"])
    if k in styles:return styles[k]
    name=f"PS{len(styles)}";styles[k]=name
    if pd["type"] in ("thru_hole","np_thru_hole"):
        p=ET.SubElement(PSS,"PadStyle",{"Name":name,"Type":"Through","HoleType":"Round","Hole":f(pd["drill"] or min(pd["sx"],pd["sy"])),"Side":"Top"})
        ET.SubElement(p,"MainStack",{"Shape":"Ellipse","Width":f(pd["sx"]),"Height":f(pd["sy"]),"XOff":"0","YOff":"0"})
    else:
        p=ET.SubElement(PSS,"PadStyle",{"Name":name,"Type":"Surface","Side":"Top"})
        ET.SubElement(p,"MainStack",{"Shape":"Rectangle","Width":f(pd["sx"]),"Height":f(pd["sy"]),"XOff":"0","YOff":"0"})
        ET.SubElement(p,"MaskPaste",{"TopMask":"Common","BotMask":"Common","TopPaste":"Common","BotPaste":"Common"})
    return name

for ci,z in enumerate(infos):
    minx=min(p["x"]-p["sx"]/2 for p in z["pads"]);maxx=max(p["x"]+p["sx"]/2 for p in z["pads"])
    miny=min(p["y"]-p["sy"]/2 for p in z["pads"]);maxy=max(p["y"]+p["sy"]/2 for p in z["pads"])
    pref=re.match(r"[A-Za-z]+",z["ref"]);pref=pref.group(0) if pref else ""
    pat=ET.SubElement(PATS,"Pattern",{"PatternStyle":f"PatType{ci}","Id":str(ci),"RefDes":pref,
        "Mounting":"Through" if any(p["type"]!="smd" for p in z["pads"]) else "SMD",
        "Width":f(maxx-minx+1),"Height":f(maxy-miny+1),"Orientation":"0","LockTypeChange":"Y","Type":"Free",
        "Float1":"0","Float2":"0","Float3":"0","Int1":"0","Int2":"0"})
    ET.SubElement(pat,"Name").text=z["name"].replace("Custom:","")
    ET.SubElement(pat,"Name_Unique").text="7313294_"+z["ref"]
    ET.SubElement(pat,"Value").text=z["val"] or z["name"]
    ET.SubElement(pat,"Origin",{"X":"0","Y":"0","Cross":"Y","Circle":"Y","Common":"Hide","Courtyard":"Show"})
    ET.SubElement(pat,"DefPad",{"Style":style(z["pads"][0])})
    ps=ET.SubElement(pat,"Pads")
    for pi,pd in enumerate(z["pads"],1):
        e=ET.SubElement(ps,"Pad",{"Id":str(pi),"Style":style(pd),"X":f(pd["x"]),"Y":f(pd["y"]),"Angle":f(math.radians(pd["a"])),"Locked":"N","Side":"Top"})
        ET.SubElement(e,"Number").text=pd["num"] or str(pi)
    ET.SubElement(pat,"Shapes")

B=ET.SubElement(R,"Board")
bo=ET.SubElement(B,"BoardOutline",{"Locked":"N","Selected":"N"});bp=ET.SubElement(bo,"Points")
for x,y in ((0,0),(100,0),(100,80),(0,80)):ET.SubElement(bp,"Point",{"X":f(x),"Y":f(y)})
S=ET.SubElement(B,"Settings");ET.SubElement(S,"Routing",{"TraceWidth":"0.25","TraceClearance":"0.25","ViaSize":"0.8","ViaHole":"0.4"})
CL=ET.SubElement(B,"CopperLayers")
for i,n in ((0,"Top"),(1,"Bottom")):
    x=ET.SubElement(CL,"Lay",{"Id":str(i),"Type":"Signal"});ET.SubElement(x,"Name").text=n
VS=ET.SubElement(B,"ViaStyles")
vstyles={}
def vst(size,hole):
    k=(round(size,6),round(hole,6))
    if k not in vstyles:
        i=len(vstyles);vstyles[k]=i;x=ET.SubElement(VS,"ViaStyle",{"Id":str(i),"Size":f(size),"HoleSize":f(hole)});ET.SubElement(x,"Name").text=f"VIA_{f(size)}_{f(hole)}"
    return vstyles[k]
vst(.8,.4);vst(1.2,.6)
NC=ET.SubElement(B,"NetClasses");nc=ET.SubElement(NC,"NetClass",{"Id":"0","UpdateId":"0","Type":"Normal","AllLayers":"Y","CheckLength":"N","AllVias":"Y","PerformDRC":"Y","LengthDelta":"2.54","FixedLength":"0","MaxUncoupledLength":"10","Tolerance":"2"});ET.SubElement(nc,"Name").text="Default"
LP=ET.SubElement(nc,"LayProperties")
for n in ("Top","Bottom"):
    x=ET.SubElement(LP,"LayProperty",{"Width":"0.25","MinWidth":"0.2","MaxWidth":"2","Clearance":"0.25","Neck_Width":"0.2","Neck_DifClearance":"0.25","Neck_MaxLength":"3","DifClearance":"0.25"});ET.SubElement(x,"LayerName").text=n
D=ET.SubElement(B,"DRC",{"CheckClearance":"Y","CheckNetConnectivity":"Y"});LC=ET.SubElement(D,"LayClearances");LS=ET.SubElement(D,"LaySizes")
for i in (0,1):
    ET.SubElement(LC,"LayClearance",{"Lay":str(i),"TraceToTrace":"0.25","TraceToPad":"0.25"})
    ET.SubElement(LS,"LaySize",{"Lay":str(i),"MinTrace":"0.2","MinDrill":"0.3","MinRing":"0.1"})
ET.SubElement(B,"ConnectivityCheck",{"Traces":"Y","Shapes":"Y","CopperPours":"Y"})

CE=ET.SubElement(B,"Components")
for ci,z in enumerate(infos):
    c=ET.SubElement(CE,"Component",{"Id":str(ci),"UpdateId":str(100+ci),"PatternStyle":f"PatType{ci}","X":f(z["x"]),"Y":f(z["y"]),"Side":"Top","Locked":"N","Selected":"N"})
    ET.SubElement(c,"RefDes").text=z["ref"];ET.SubElement(c,"Name").text=z["name"].replace("Custom:","");ET.SubElement(c,"Value").text=z["val"] or z["name"]
    cp=ET.SubElement(c,"Pads")
    for pi,pd in enumerate(z["pads"],1):ET.SubElement(cp,"Pad",{"Id":str(pi),"NetId":str(pd["net"]-1) if pd["net"]>0 else "-1","InternalConnection":"-1"})
base=len(infos)
for vi,v in enumerate(vias,1):
    x,y,size,hole,net=viainfo(v);cid=base+vi-1
    c=ET.SubElement(CE,"Component",{"Id":str(cid),"Type":"Via","ViaStyle":str(vst(size,hole)),"X":f(x),"Y":f(y),"Locked":"N","Selected":"N"})
    ET.SubElement(c,"RefDes").text=f"V{vi}";ET.SubElement(c,"Name").text="Routing via";p=ET.SubElement(c,"Pads");ET.SubElement(p,"Pad",{"Id":"1","NetId":str(net-1)})
ET.SubElement(B,"Ratlines")
NE=ET.SubElement(B,"Nets")
for kid in sorted(nets):
    ne=ET.SubElement(NE,"Net",{"Id":str(kid-1),"HiddenId":str(kid-1),"NetClass":"0","Locked":"N","RouteMode":"Ratlines"});ET.SubElement(ne,"Name").text=nets[kid]
    pads=ET.SubElement(ne,"Pads")
    for ci,z in enumerate(infos):
        for pi,pd in enumerate(z["pads"],1):
            if pd["net"]==kid:ET.SubElement(pads,"Item",{"Comp":str(ci),"Pad":str(pi)})
    trs=ET.SubElement(ne,"Traces");tid=0
    for s in segs:
        x1,y1,x2,y2,w,layer,n=seginfo(s)
        if n!=kid:continue
        tr=ET.SubElement(trs,"Trace",{"Id":str(tid),"Connected1":"None","Connected2":"None","Group":"-1","PairSeparateTrace":"-1","Selected":"N","Locked":"N"});pp=ET.SubElement(tr,"Points");lay="0" if layer=="F.Cu" else "1"
        ET.SubElement(pp,"Point",{"Id":"0","X":f(x1),"Y":f(y1),"Lay":lay,"Width":f(w),"Jumper":"0","Arc":"N","ViaStyle":"-1","Selected":"N"})
        ET.SubElement(pp,"Point",{"Id":"1","X":f(x2),"Y":f(y2),"Lay":lay,"Width":f(w),"Jumper":"0","Arc":"N","ViaStyle":"-1","Selected":"N"});tid+=1
ET.SubElement(B,"DifferentialPairs");ET.SubElement(B,"CopperPours");ET.SubElement(B,"Shapes")
ET.indent(R,space="  ")
OUT.write_bytes(ET.tostring(R,encoding="utf-8",xml_declaration=True))
print("DIPXML",OUT,OUT.stat().st_size,hashlib.sha256(OUT.read_bytes()).hexdigest(),"components",len(infos),"vias",len(vias),"nets",len(nets),"segments",len(segs))
