import bpy, math, os, json
from mathutils import Vector

ROOT=os.path.abspath('case4')
SRC=os.path.join(ROOT,'source'); EXP=os.path.join(ROOT,'exports'); SH=os.path.join(ROOT,'screenshots'); LOG=os.path.join(ROOT,'logs')
for p in [SRC,EXP,SH,LOG]: os.makedirs(p,exist_ok=True)

bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Original profile based on the student's own sketch, dimensions in meters.
PROFILE=[
    (0.000,0.000),(0.060,0.000),(0.066,0.006),(0.061,0.014),
    (0.026,0.026),(0.019,0.040),(0.018,0.078),(0.026,0.092),
    (0.052,0.105),(0.071,0.120),(0.081,0.155),(0.083,0.198),
    (0.080,0.222),(0.073,0.231),(0.066,0.231),(0.070,0.218),
    (0.071,0.198),(0.068,0.158),(0.059,0.130),(0.046,0.112),
    (0.023,0.098),(0.013,0.082),(0.012,0.034),(0.000,0.020)
]

def resample(points,n):
    ds=[0.0]
    for i in range(1,len(points)):
        a=Vector(points[i-1]); b=Vector(points[i]); ds.append(ds[-1]+(b-a).length)
    total=ds[-1]; out=[]
    for k in range(n):
        t=total*k/(n-1); j=1
        while j<len(ds) and ds[j] < t: j+=1
        j=min(j,len(ds)-1); d0,d1=ds[j-1],ds[j]
        q=0.0 if d1==d0 else (t-d0)/(d1-d0)
        out.append((points[j-1][0]*(1-q)+points[j][0]*q, points[j-1][1]*(1-q)+points[j][1]*q))
    return out

def lathe(name, profile, segments):
    verts=[]; faces=[]; rings=len(profile)
    for s in range(segments):
        a=2*math.pi*s/segments; ca,sa=math.cos(a),math.sin(a)
        for r,z in profile:
            verts.append((r*ca,r*sa,z))
    for s in range(segments):
        ns=(s+1)%segments
        for j in range(rings-1):
            faces.append((s*rings+j, ns*rings+j, ns*rings+j+1, s*rings+j+1))
    me=bpy.data.meshes.new(name+'Mesh'); me.from_pydata(verts,[],faces); me.update()
    ob=bpy.data.objects.new(name,me); bpy.context.collection.objects.link(ob)
    # Predictable cylindrical UV topology: one continuous strip around the rotational axis.
    uv=me.uv_layers.new(name='UVMap')
    for poly in me.polygons:
        for li in poly.loop_indices:
            vi=me.loops[li].vertex_index; s=vi//rings; j=vi%rings
            uv.data[li].uv=(s/segments, j/(rings-1))
    for p in me.polygons: p.use_smooth=True
    return ob

low=lathe('Goblet_LOW',PROFILE,32)
high=lathe('Goblet_HIGH',resample(PROFILE,72),160)
high.hide_viewport=True; high.hide_render=True

# Original PBR-like material maps.
albedo=bpy.data.images.load(os.path.join(SRC,'goblet_albedo.png'))
rough=bpy.data.images.load(os.path.join(SRC,'goblet_roughness.png'))
mat=bpy.data.materials.new('Aged_Brass_Patina'); mat.use_nodes=True
nodes=mat.node_tree.nodes; links=mat.node_tree.links
bsdf=nodes.get('Principled BSDF')
tex=nodes.new('ShaderNodeTexImage'); tex.image=albedo; tex.label='Original Albedo 1024'
rtex=nodes.new('ShaderNodeTexImage'); rtex.image=rough; rtex.image.colorspace_settings.name='Non-Color'; rtex.label='Original Roughness 1024'
links.new(tex.outputs['Color'],bsdf.inputs['Base Color'])
links.new(rtex.outputs['Color'],bsdf.inputs['Roughness'])
bsdf.inputs['Metallic'].default_value=0.78
low.data.materials.append(mat); high.data.materials.append(mat)

# High-poly-only details: four rings with dense circular topology.
details=[]
for z,major,minor in [(0.022,0.052,0.0036),(0.094,0.030,0.0032),(0.119,0.061,0.0027),(0.213,0.078,0.0026)]:
    bpy.ops.mesh.primitive_torus_add(major_radius=major,minor_radius=minor,major_segments=96,minor_segments=16,location=(0,0,z))
    o=bpy.context.object; o.name='HIGH_Detail_Ring_%03d'%int(z*1000); o.data.materials.append(mat)
    o.hide_viewport=True; o.hide_render=True; details.append(o)

# Custom metadata for scale verification.
low['asset_role']='game_low_poly'; low['units']='meters'; low['height_m']=0.231
high['asset_role']='high_poly_source'; high['units']='meters'; high['height_m']=0.231

stats={
    'low_vertices':len(low.data.vertices), 'low_edges':len(low.data.edges), 'low_polygons':len(low.data.polygons),
    'high_vertices':len(high.data.vertices), 'high_edges':len(high.data.edges), 'high_polygons':len(high.data.polygons),
    'high_detail_polygons':sum(len(o.data.polygons) for o in details),
    'height_m':0.231, 'bowl_diameter_m':0.166, 'base_diameter_m':0.132,
    'uv_layers':len(low.data.uv_layers), 'material_name':mat.name
}
with open(os.path.join(LOG,'mesh_stats.json'),'w') as f: json.dump(stats,f,indent=2)
# Save UV loop coordinates for an exact layout drawing outside Blender.
uv_edges=[]
uv=low.data.uv_layers.active.data
for poly in low.data.polygons:
    coords=[tuple(uv[li].uv) for li in poly.loop_indices]
    for i in range(len(coords)):
        uv_edges.append((coords[i],coords[(i+1)%len(coords)]))
with open(os.path.join(LOG,'uv_edges.json'),'w') as f: json.dump(uv_edges,f)
print('CASE4_STATS',json.dumps(stats))

# Save master file before render rig is added.
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SRC,'7334625_Case4_Goblet_Master.blend'))

# Game exports contain only optimized low-poly object.
bpy.ops.object.select_all(action='DESELECT'); low.hide_viewport=False; low.hide_render=False; low.select_set(True); bpy.context.view_layer.objects.active=low
bpy.ops.export_scene.gltf(filepath=os.path.join(EXP,'7334625_Goblet_LOW.glb'), export_format='GLB', use_selection=True, export_apply=True)
try:
    bpy.ops.export_scene.fbx(filepath=os.path.join(EXP,'7334625_Goblet_LOW.fbx'), use_selection=True, apply_unit_scale=True, global_scale=1.0)
except Exception as e:
    print('FBX_WARNING',repr(e))

# Studio rig for real Blender renders.
bpy.ops.object.select_all(action='DESELECT')
bpy.ops.mesh.primitive_plane_add(size=2,location=(0,0,-0.003)); floor=bpy.context.object; floor.name='Studio_Floor'
fm=bpy.data.materials.new('StudioFloor'); fm.diffuse_color=(0.035,0.04,0.05,1); floor.data.materials.append(fm)
bpy.ops.object.camera_add(location=(0.36,-0.40,0.29)); cam=bpy.context.object; bpy.context.scene.camera=cam; cam.data.lens=58

def point_at(obj, pt):
    obj.rotation_euler=(Vector(pt)-obj.location).to_track_quat('-Z','Y').to_euler()
point_at(cam,(0,0,0.12))
for loc,energy,size,col in [((0.24,-0.22,0.43),780,0.23,(1.0,0.72,0.43)),((-0.27,-0.08,0.29),520,0.25,(0.42,0.66,1.0)),((0.04,0.30,0.35),430,0.20,(0.45,1.0,0.82))]:
    bpy.ops.object.light_add(type='AREA',location=loc); l=bpy.context.object; l.data.energy=energy; l.data.shape='DISK'; l.data.size=size; l.data.color=col; point_at(l,(0,0,0.12))
sc=bpy.context.scene
try: sc.render.engine='BLENDER_EEVEE_NEXT'
except Exception: sc.render.engine='BLENDER_EEVEE'
sc.render.resolution_x=1100; sc.render.resolution_y=1100; sc.render.resolution_percentage=100
sc.render.image_settings.file_format='PNG'; sc.world.color=(0.008,0.012,0.018)

# Textured low-poly stage.
low.hide_render=False; high.hide_render=True
for o in details: o.hide_render=True
sc.render.filepath=os.path.join(SH,'06_Textured_View.png'); bpy.ops.render.render(write_still=True)

# Final render: low-poly game asset, production lighting.
cam.location=(0.32,-0.37,0.23); point_at(cam,(0,0,0.115)); sc.render.filepath=os.path.join(SH,'07_Final_Render.png'); bpy.ops.render.render(write_still=True)

# High-poly source render: dense surface plus detail rings.
low.hide_render=True; high.hide_render=False
for o in details: o.hide_render=False
neutral=bpy.data.materials.new('HighPoly_Clay'); neutral.use_nodes=True
nbsdf=neutral.node_tree.nodes.get('Principled BSDF'); nbsdf.inputs['Base Color'].default_value=(0.30,0.34,0.38,1); nbsdf.inputs['Metallic'].default_value=0.0; nbsdf.inputs['Roughness'].default_value=0.52
high.data.materials.clear(); high.data.materials.append(neutral)
for o in details: o.data.materials.clear(); o.data.materials.append(neutral)
sc.render.filepath=os.path.join(SH,'04_HighPoly_View.png'); bpy.ops.render.render(write_still=True)

# Restore low and save render scene.
low.hide_render=False; high.hide_render=True
for o in details: o.hide_render=True
low.data.materials.clear(); low.data.materials.append(mat)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(SRC,'7334625_Case4_Goblet_RenderScene.blend'))
print('CASE4 BLENDER BUILD: PASS')
