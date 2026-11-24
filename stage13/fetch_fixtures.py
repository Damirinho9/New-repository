"""Fetch public, licensed comparison fixtures only. No KOMPAS runtime or student data."""
import hashlib, io, json, pathlib, urllib.parse, urllib.request, zipfile, zlib, re
out=pathlib.Path("fixture-output");out.mkdir(exist_ok=True)
bot="vdnrobo/Botix-KOMPAS/6246c08693f1d2b88a23c3cf0e0bc404ebcfdde5/"
frw="Chumakov-Anton-I/ks2svg_py/c5e77164832e49dbb7b8648ae558345d4bf58bab/"
files=[
("bushing.m3d",bot+"Models/Конструктив/Втулка/.m3d","9011cca8d47612c60e62f31cf7f2abea86f417c1"),
("bushing.step",bot+"Models/Конструктив/Втулка/.m3d.stp","893d480a5940018cd9125a2f262aa098806f9ee0"),
("wheel-assembly.a3d",bot+"Models/Колесо/D52/.a3d","4b267dc45eb03ab127de06efa34c17ce35dadf24"),
("LICENSE-Botix.txt",bot+"LICENSE","84a6d46827644b09ad5fba73b8fa9484bcbb2bdb"),
("sample.frw",frw+"SAMPLE.frw","c4a002219d82eb3f4effd80737e1b10595395561"),
("LICENSE-ks2svg.txt",frw+"LICENSE",None),
]
records=[]
for name,path,expected in files:
    url="https://raw.githubusercontent.com/"+urllib.parse.quote(path)
    with urllib.request.urlopen(url,timeout=25) as r: b=r.read(4*1024*1024)
    blob=hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
    if expected and blob!=expected: raise RuntimeError("git blob hash mismatch "+name)
    (out/name).write_bytes(b)
    row={"file":name,"source":url,"git_blob":blob,"sha256":hashlib.sha256(b).hexdigest(),"size":len(b)}
    if zipfile.is_zipfile(io.BytesIO(b)):
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            assert z.testzip() is None
            row["entries"]={i.filename:i.file_size for i in z.infolist()}
            row["zip_crc_pass"]=True
            if "Contents" in z.namelist():
                data=z.read("Contents");pos=2 if data.startswith(b"KF") else 0;blocks=[]
                while pos+2<len(data):
                    try:
                        d=zlib.decompressobj();raw=d.decompress(data[pos:],64*1024*1024)
                        if not d.eof or d.unconsumed_tail:break
                        n=len(data[pos:])-len(d.unused_data)
                        if n<=0:break
                        blocks.append({"offset":pos,"encoded":n,"decoded":len(raw),"sha256":hashlib.sha256(raw).hexdigest()});pos+=n
                    except zlib.error:break
                row["contiguous_zlib_blocks"]=blocks;row["remaining_bytes"]=len(data)-pos
    records.append(row);print(name,len(b),blob,flush=True)
(out/"manifest.json").write_text(json.dumps({"status":"PUBLIC_FIXTURE_COLLECTION_ONLY","files":records,"licenses":{"Botix":"GPL-3.0","ks2svg":"Apache-2.0"}},indent=2),encoding="utf-8")
