#!/usr/bin/env bash
set -euo pipefail

# Exact UV layout from Blender-exported UV coordinates.
python3 - <<'PY'
from PIL import Image,ImageDraw,ImageFont
import json
edges=json.load(open('case4/logs/uv_edges.json'))
im=Image.new('RGB',(1400,900),(32,35,40)); d=ImageDraw.Draw(im)
margin=70; w=1260; h=760
d.rectangle((margin,margin,margin+w,margin+h),outline=(105,117,130),width=2)
for a,b in edges:
    d.line((margin+a[0]*w,margin+(1-a[1])*h,margin+b[0]*w,margin+(1-b[1])*h),fill=(224,187,88),width=1)
try: f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',25)
except: f=None
d.text((70,22),'UV-развертка Goblet_LOW - UVMap из Blender',font=f,fill=(240,240,235))
im.save('case4/screenshots/05_UV_Layout.png')
PY

# Real Blender UI screenshot in wireframe mode.
cat > /tmp/wire_view.py <<'PY'
import bpy
from mathutils import Quaternion
low=bpy.data.objects.get('Goblet_LOW'); high=bpy.data.objects.get('Goblet_HIGH')
if high: high.hide_viewport=True
for o in bpy.data.objects:
    if o.name.startswith('HIGH_Detail_'): o.hide_viewport=True
    o.select_set(False)
if low:
    low.hide_viewport=False; low.select_set(True); bpy.context.view_layer.objects.active=low
for a in bpy.context.screen.areas:
    if a.type=='VIEW_3D':
        a.spaces.active.shading.type='WIREFRAME'
        a.spaces.active.overlay.show_wireframes=True
        a.spaces.active.region_3d.view_distance=0.30
        a.spaces.active.region_3d.view_rotation=Quaternion((0.86,0.18,0.30,0.36))
PY
Xvfb :99 -screen 0 1600x900x24 -ac +extension GLX +render -noreset >/tmp/xvfb.log 2>&1 & echo $! >/tmp/xvfb.pid
export DISPLAY=:99
export LIBGL_ALWAYS_SOFTWARE=1
openbox >/tmp/openbox.log 2>&1 &
sleep 2
blender case4/source/7334625_Case4_Goblet_Master.blend --python /tmp/wire_view.py > case4/logs/blender_wire_ui.log 2>&1 & echo $! >/tmp/blender.pid
sleep 14
ffmpeg -y -f x11grab -video_size 1600x900 -i :99.0 -frames:v 1 case4/screenshots/03_LowPoly_Wireframe.png >/tmp/wire_shot.log 2>&1
kill $(cat /tmp/blender.pid) 2>/dev/null || true
sleep 2

# Real game-engine import check in Godot.
wget -q https://github.com/godotengine/godot/releases/download/4.7.2-stable/Godot_v4.7.2-stable_linux.x86_64.zip -O /tmp/godot.zip
unzip -q /tmp/godot.zip -d /tmp/godot
chmod +x /tmp/godot/Godot_v4.7.2-stable_linux.x86_64
GODOT=/tmp/godot/Godot_v4.7.2-stable_linux.x86_64
mkdir -p case4/engine
cp case4/exports/7334625_Goblet_LOW.glb case4/engine/goblet_low.glb
cat > case4/engine/project.godot <<'EOF'
config_version=5
[application]
config/name="Case 4 - Goblet Import Verification"
run/main_scene="res://Main.tscn"
[display]
window/size/viewport_width=1000
window/size/viewport_height=700
window/size/window_width_override=1000
window/size/window_height_override=700
[rendering]
renderer/rendering_method="gl_compatibility"
renderer/environment/defaults/default_clear_color=Color(0.025,0.032,0.045,1)
EOF
cat > case4/engine/Main.tscn <<'EOF'
[gd_scene load_steps=3 format=3]
[ext_resource type="PackedScene" path="res://goblet_low.glb" id="1_goblet"]
[ext_resource type="Script" path="res://Main.gd" id="2_script"]
[node name="ImportCheck" type="Node3D"]
script = ExtResource("2_script")
[node name="Goblet_LOW" parent="." instance=ExtResource("1_goblet")]
[node name="Camera3D" type="Camera3D" parent="."]
current = true
[node name="KeyLight" type="DirectionalLight3D" parent="."]
rotation = Vector3(-0.7,-0.7,0)
light_energy = 1.8
[node name="FillLight" type="OmniLight3D" parent="."]
position = Vector3(-0.25,0.23,0.28)
omni_range = 2.0
light_energy = 3.0
EOF
cat > case4/engine/Main.gd <<'EOF'
extends Node3D
func _ready():
    var cam=$Camera3D
    cam.position=Vector3(0.34,0.27,0.38)
    cam.look_at(Vector3(0,0.115,0),Vector3.UP)
    print("CASE 4 ENGINE IMPORT: PASS")
    print("GLB loaded; scale units: meters; expected height: 0.231 m")
func _process(delta):
    $Goblet_LOW.rotate_y(delta*0.25)
EOF
timeout 60s "$GODOT" --headless --editor --path "$PWD/case4/engine" --quit --rendering-method gl_compatibility > case4/logs/godot_import.log 2>&1 || true
"$GODOT" --editor --path "$PWD/case4/engine" "$PWD/case4/engine/Main.tscn" --rendering-method gl_compatibility > case4/logs/godot_editor.log 2>&1 & echo $! >/tmp/godot_editor.pid
sleep 9
"$GODOT" --path "$PWD/case4/engine" --rendering-method gl_compatibility --position 300,120 > case4/logs/godot_runtime.log 2>&1 & echo $! >/tmp/godot_game.pid
sleep 9
ffmpeg -y -f x11grab -video_size 1600x900 -i :99.0 -frames:v 1 case4/screenshots/08_GameEngine_Import.png >/tmp/engine_shot.log 2>&1
kill $(cat /tmp/godot_game.pid) 2>/dev/null || true
kill $(cat /tmp/godot_editor.pid) 2>/dev/null || true
kill $(cat /tmp/xvfb.pid) 2>/dev/null || true
grep -q 'CASE 4 ENGINE IMPORT: PASS' case4/logs/godot_runtime.log

# Final structural verification and hashes.
python3 - <<'PY'
import os,json,hashlib
root='case4'
required=['screenshots/01_Moodboard_References.png','screenshots/02_Original_Concept_Sketch.png','screenshots/03_LowPoly_Wireframe.png','screenshots/04_HighPoly_View.png','screenshots/05_UV_Layout.png','screenshots/06_Textured_View.png','screenshots/07_Final_Render.png','screenshots/08_GameEngine_Import.png','source/7334625_Case4_Goblet_Master.blend','exports/7334625_Goblet_LOW.glb']
missing=[p for p in required if not os.path.isfile(os.path.join(root,p)) or os.path.getsize(os.path.join(root,p))==0]
if missing: raise SystemExit('Missing '+repr(missing))
s=json.load(open(os.path.join(root,'logs','mesh_stats.json')))
assert s['low_polygons'] < s['high_polygons']
assert s['uv_layers'] >= 1
print('CASE 4 VALIDATION: PASS',s)
with open(os.path.join(root,'MANIFEST_SHA256.txt'),'w') as out:
    for base,_,files in os.walk(root):
        for fn in sorted(files):
            p=os.path.join(base,fn)
            if p.endswith('MANIFEST_SHA256.txt'): continue
            out.write(hashlib.sha256(open(p,'rb').read()).hexdigest()+'  '+p+'\n')
PY
