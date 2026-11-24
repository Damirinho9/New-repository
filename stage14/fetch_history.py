import pathlib,urllib.request,urllib.parse,hashlib,json
out=pathlib.Path('history-output');out.mkdir()
root='Models/Конструктив/Втулка/'
rows=[
('old1.m3d','6691a3072e9384ba151edee3b97fd6b242018159','.m3d','cea08991581d70ed10eaf094efa3875ac2cb486c'),
('old2.m3d','af3ab05d1a50b391bdd62b96502e658ed0e0b0ed','.m3d','167363ab2b5ce31096d52d7481dc28408ffec89d'),
('old-M3x2.step','6691a3072e9384ba151edee3b97fd6b242018159','М3x2.stp','08146ee89d5f77564c54304a0cc1ba99b3a46d21'),
('old-M3x6.step','6691a3072e9384ba151edee3b97fd6b242018159','M3x6.stp','435e92654bda22e2028207ea4cfe8385004429b7'),
('current-M3x6.step','c643a86d6fe6734e23a535785feeee873d51d9d6','M3x6.stp','794291ce529157c730c1ac31044f7c4cb39eb985')]
manifest=[]
for name,commit,path,expected in rows:
    url='https://raw.githubusercontent.com/vdnrobo/Botix-KOMPAS/'+commit+'/'+urllib.parse.quote(root+path)
    with urllib.request.urlopen(url,timeout=25) as r: data=r.read(2000000)
    assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==expected
    (out/name).write_bytes(data)
    manifest.append(dict(file=name,commit=commit,git_blob=expected,sha256=hashlib.sha256(data).hexdigest(),size=len(data),url=url))
    print(name,len(data),flush=True)
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
(out/'SOURCE.txt').write_text('Botix-KOMPAS GPL-3.0, original public research fixtures only; license https://github.com/vdnrobo/Botix-KOMPAS/blob/main/LICENSE\n')
