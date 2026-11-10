from PIL import Image, ImageDraw, ImageFont
import os, random, math

ROOT = os.path.abspath('case4')
REF = os.path.join(ROOT, 'refs')
SRC = os.path.join(ROOT, 'source')
SH = os.path.join(ROOT, 'screenshots')
os.makedirs(REF, exist_ok=True)
os.makedirs(SRC, exist_ok=True)
os.makedirs(SH, exist_ok=True)

def font(size):
    candidates = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf',
    ]
    for p in candidates:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

# Moodboard based only on downloaded public/reference images.
items = [
    ('met_chalice.jpg', 'Форма чаши и ножки', 'The Metropolitan Museum of Art'),
    ('public_domain_goblet.jpg', 'Силуэт и пропорции', 'PICRYL / public domain'),
    ('clock_tower.jpg', 'Сеттинг и мотив времени', 'Wikimedia Commons'),
]
canvas = Image.new('RGB', (1600, 900), (27, 30, 34))
d = ImageDraw.Draw(canvas)
d.text((45, 30), 'MOODBOARD - вариант 20: кубок / "Город, затерянный во времени"', font=font(28), fill=(240,240,235))
x = 45
loaded = 0
for fn, label, source in items:
    p = os.path.join(REF, fn)
    if not os.path.isfile(p) or os.path.getsize(p) < 1000:
        continue
    try:
        im = Image.open(p).convert('RGB')
    except Exception:
        continue
    im.thumbnail((470, 620))
    y = 120 + (620 - im.height)//2
    canvas.paste(im, (x, y))
    d.rectangle((x-3,y-3,x+im.width+3,y+im.height+3), outline=(179,150,87), width=3)
    d.text((x, 755), label, font=font(19), fill=(238,232,214))
    d.text((x, 785), source, font=font(14), fill=(172,185,193))
    x += 510
    loaded += 1
if loaded == 0:
    raise SystemExit('No reference images downloaded')
d.text((45, 850), 'Направление: состаренная латунь, зеленоватая патина, следы времени, мотивы циферблата. Финальная модель оригинальна.', font=font(18), fill=(190,200,205))
canvas.save(os.path.join(SH, '01_Moodboard_References.png'))

# Original concept sketch, drawn from scratch.
sk = Image.new('RGB', (1200, 900), 'white')
sd = ImageDraw.Draw(sk)
sd.text((40, 30), 'Собственный эскиз - "Кубок Хранителя Времени"', font=font(28), fill=(25,25,25))
cx = 560
profile = [(cx-58,750),(cx-100,730),(cx-112,690),(cx-48,648),(cx-22,607),(cx-22,455),(cx-58,430),(cx-140,390),(cx-177,300),(cx-184,185),(cx-174,145)]
rprofile = [(2*cx-x,y) for x,y in reversed(profile)]
out = profile+rprofile
sd.line(out+[out[0]], fill=(60,60,60), width=5)
sd.ellipse((cx-184,125,cx+184,165), outline=(60,60,60), width=4)
sd.ellipse((cx-112,720,cx+112,772), outline=(60,60,60), width=4)
# clock motif
sd.ellipse((cx-60,470,cx+60,590), outline=(90,90,90), width=4)
for a in range(0,360,30):
    ang=math.radians(a)
    sd.line((cx+39*math.cos(ang),530+39*math.sin(ang),cx+55*math.cos(ang),530+55*math.sin(ang)), fill=(90,90,90), width=3)
sd.line((cx,530,cx+28,505),fill=(90,90,90),width=4)
sd.line((cx,530,cx-5,492),fill=(90,90,90),width=4)
# annotations
sd.line((cx+180,220,850,220), fill=(60,60,60), width=2)
sd.text((870,195), 'Широкая чаша', font=font(19), fill=(20,20,20))
sd.text((870,222), 'с потертым ободом', font=font(17), fill=(70,70,70))
sd.line((cx+60,530,820,530), fill=(60,60,60), width=2)
sd.text((840,505), 'Мотив циферблата', font=font(19), fill=(20,20,20))
sd.text((840,532), 'на центральном узле', font=font(17), fill=(70,70,70))
sd.line((cx+105,730,820,690), fill=(60,60,60), width=2)
sd.text((840,665), 'Устойчивая база', font=font(19), fill=(20,20,20))
sd.text((40,815), 'Габарит: высота 0,231 м; чаша 0,166 м; основание 0,132 м.', font=font(18), fill=(25,25,25))
sd.text((40,850), 'Материал: состаренная латунь с патиной. Стиль: реалистичная игровая стилизация.', font=font(18), fill=(25,25,25))
sk.save(os.path.join(SH, '02_Original_Concept_Sketch.png'))

# Original albedo texture generated procedurally, not AI-generated.
random.seed(7334625)
W=1024; H=1024
tex=Image.new('RGB',(W,H),(128,94,41)); td=ImageDraw.Draw(tex)
for y in range(H):
    for x in range(0,W,4):
        n=random.randint(-17,17)
        td.rectangle((x,y,x+3,y), fill=(max(0,min(255,128+n)), max(0,min(255,94+n)), max(0,min(255,41+n))))
for _ in range(260):
    x=random.randrange(W); y=random.randrange(H); rx=random.randrange(4,42); ry=max(2,rx//3)
    td.ellipse((x-rx,y-ry,x+rx,y+ry), fill=random.choice([(39,84,72),(48,101,82),(31,70,64),(65,106,76)]))
for x in range(0,W,42):
    td.rectangle((x,72,x+4,136), fill=(57,46,29))
for _ in range(150):
    x=random.randrange(W); y=random.randrange(H); ln=random.randrange(20,150)
    td.line((x,y,min(W-1,x+ln),min(H-1,y+random.randrange(-6,7))), fill=(72,58,32), width=1)
tex.save(os.path.join(SRC,'goblet_albedo.png'))

# Roughness map: aged/patina areas rougher.
rough=Image.new('L',(W,H),150); rd=ImageDraw.Draw(rough)
random.seed(7334626)
for _ in range(300):
    x=random.randrange(W); y=random.randrange(H); r=random.randrange(5,45)
    rd.ellipse((x-r,y-r//3,x+r,y+r//3), fill=random.randrange(175,235))
rough.save(os.path.join(SRC,'goblet_roughness.png'))

with open(os.path.join(REF,'SOURCES.txt'),'w',encoding='utf-8') as f:
    f.write('Reference 1: The Metropolitan Museum of Art, German Chalice, image DP366852.jpg.\n')
    f.write('Reference 2: PICRYL public-domain Gold Goblet, media gold-goblet-da09c2.\n')
    f.write('Reference 3: Wikimedia Commons, Clock Tower in Kotor.JPG, setting/aging reference.\n')
    f.write('References are used only for research/moodboard. Sketch, texture and 3D model are original work.\n')
print('CASE4 REFS: PASS loaded=',loaded)
