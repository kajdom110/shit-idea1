"""Path-traced render of the tar with Blender Cycles (spec section 15, phases R2–R4).

Builds the scene from build/tar.obj (exported by export_model.mjs) and the CC0 assets
(fetch_assets.py): physical materials, soft room light from an HDRI with a dark backdrop,
and a camera that follows the same scroll scenes as the web page (build/scenes.json).

    python3 render/build_scene.py test                  # one still per scroll scene, small
    python3 render/build_scene.py scroll 0 239          # scroll frames 0…239 (inclusive)
    python3 render/build_scene.py sheet                 # rotation sheet: 24 turns × 5 tilts

Coordinates: the web model is in centimetres, y up, skin facing +z. Blender is in metres,
z up; the import maps web (x, y, z) to Blender (x, -z, y) at 0.01 scale, so the skin faces -y
and the camera looks along +y.
"""
import json
import math
import os
import sys
import time
from pathlib import Path

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

HERE = Path(__file__).resolve().parent
BUILD = HERE / 'build'
ASSETS = HERE / 'assets'
WEB_TEX = HERE.parent / 'tar3d' / 'textures'
CM = 0.01
# Polish of the body wood, 0 (raw, matte) … 1 (a thin, satin oil-and-wax finish: the
# user's choice after comparing both, spec section 16). TAR_GLOSS=0 renders the matte variant.
GLOSS = float(os.environ.get('TAR_GLOSS', '1'))

SCENES = json.loads((BUILD / 'scenes.json').read_text())
PIVOT_WEB = SCENES['pivot']


def web_to_blender(p):
    """Web point (cm, y up) → Blender point (m, z up)."""
    x, y, z = p
    return Vector((x * CM, -z * CM, y * CM))


PIVOT = web_to_blender((PIVOT_WEB['x'], PIVOT_WEB['y'], PIVOT_WEB['z']))


def srgb(hexstr, alpha=1.0):
    """'#rrggbb' in sRGB → linear RGBA, as Blender colour sockets expect."""
    c = [int(hexstr[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (*lin, alpha)


# ---------------------------------------------------------------- scene and import
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.device = 'CPU'
    sc.cycles.use_denoising = True
    sc.cycles.denoiser = 'OPENIMAGEDENOISE'
    sc.cycles.max_bounces = 8
    sc.cycles.transmission_bounces = 8
    sc.view_settings.view_transform = 'AgX'
    # AgX alone washes the honey wood out; the punchy look keeps its saturation
    sc.view_settings.look = 'AgX - Punchy'
    sc.render.film_transparent = False
    sc.unit_settings.system = 'METRIC'
    return sc


def import_model():
    bpy.ops.wm.obj_import(filepath=str(BUILD / 'tar.obj'), global_scale=CM,
                          forward_axis='NEGATIVE_Z', up_axis='Y', use_split_objects=True)
    objs = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    # The importer puts the cm→m scale on each object; bake it into the meshes so the
    # procedural wood (Object coordinates) works in metres.
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    # the importer's own materials (from usemtl) are replaced in build_materials
    for o in objs:
        o.data.materials.clear()
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    # One pivot at the instrument's visual centre carries every part; turning it turns the tar.
    pivot = bpy.data.objects.new('pivot', None)
    bpy.context.scene.collection.objects.link(pivot)
    pivot.location = PIVOT
    for o in objs:
        o.parent = pivot
        o.matrix_parent_inverse = Matrix.Translation(-PIVOT)
        for poly in o.data.polygons:
            poly.use_smooth = True
    return pivot, objs


# ---------------------------------------------------------------- materials
def new_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return m, nt, bsdf


def image(nt, path, colour=True):
    n = nt.nodes.new('ShaderNodeTexImage')
    n.image = bpy.data.images.load(str(path), check_existing=True)
    n.image.colorspace_settings.name = 'sRGB' if colour else 'Non-Color'
    return n


def ash_detail(nt):
    """Scanned ash veneer as a detail layer: fibres and pores, box-projected in object space
    with the grain turned to run along the instrument (Blender z). Returns a factor around 1."""
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (6.0, 6.0, 6.0)  # one 2k tile ≈ 17 cm
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    img = image(nt, ASSETS / 'ash_veneer_diff_2k_rot.jpg')
    img.projection = 'BOX'
    img.projection_blend = 0.3
    nt.links.new(mp.outputs['Vector'], img.inputs['Vector'])
    # normalise to the texture's mean brightness, then soften: detail without its pale colour
    bw = nt.nodes.new('ShaderNodeRGBToBW')
    nt.links.new(img.outputs['Color'], bw.inputs['Color'])
    norm = nt.nodes.new('ShaderNodeMath'); norm.operation = 'DIVIDE'; norm.inputs[1].default_value = 0.30
    nt.links.new(bw.outputs['Val'], norm.inputs[0])
    soft = nt.nodes.new('ShaderNodeMix'); soft.data_type = 'FLOAT'
    soft.inputs['Factor'].default_value = 0.45
    soft.inputs['A'].default_value = 1.0
    nt.links.new(norm.outputs['Value'], soft.inputs['B'])
    return soft.outputs['Result'], bw.outputs['Val']


def muted(hexcol, sat=0.9, val=0.9):
    """The same hue, a little duller (saturation × sat) and darker (value × val)."""
    import colorsys
    r, g, b = (int(hexcol[i:i + 2], 16) / 255 for i in (1, 3, 5))
    h, s_, v = colorsys.rgb_to_hsv(r, g, b)
    r, g, b = colorsys.hsv_to_rgb(h, s_ * sat, v * val)
    return '#%02x%02x%02x' % tuple(round(c * 255) for c in (r, g, b))


# golden mulberry of bowl, neck and head: round 6 colours, 10% duller and darker (round 7)
MULBERRY = tuple(muted(c) for c in ('#c98a3a', '#a05a24', '#4a2008'))


def ring_wood(name, light, mid, line, axis_cm, tilt, rings_per_cm, roughness, warp_cm=0.5,
              ramp=(0.0, 0.45, 0.72, 0.92), line_var=(0.3, 1.0), irregular=0.0):
    """Ring-porous wood: 3D growth rings round a slightly tilted log axis (so bulges show oval
    eyes, as on the reference close-ups), the scanned ash for fibres and pores, and no gloss.
    Each year's dark line has its own strength (line_var: weakest…strongest), as in real wood."""
    m, nt, bsdf = new_mat(name)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    # move the log axis to the origin, then tilt it (the web model's axis and tilt, converted)
    move = nt.nodes.new('ShaderNodeMapping')
    ax = web_to_blender((axis_cm[0], 0, axis_cm[1]))
    move.inputs['Location'].default_value = (-ax.x, -ax.y, 0)
    tilt_m = nt.nodes.new('ShaderNodeMapping')
    tilt_m.inputs['Rotation'].default_value = (math.atan(tilt[1]), -math.atan(tilt[0]), 0)
    nt.links.new(tc.outputs['Object'], move.inputs['Vector'])
    nt.links.new(move.outputs['Vector'], tilt_m.inputs['Vector'])
    N = nt.nodes.new
    def op(op, x, y=None):
        n = N('ShaderNodeMath'); n.operation = op
        for i, v in enumerate((x, y)):
            if v is None: continue
            if isinstance(v, (int, float)): n.inputs[i].default_value = v
            else: nt.links.new(v, n.inputs[i])
        return n.outputs[0]
    per_m = rings_per_cm * 100
    # distance from the (tilted) log axis, in metres
    sep = N('ShaderNodeSeparateXYZ'); nt.links.new(tilt_m.outputs['Vector'], sep.inputs[0])
    r = op('SQRT', op('ADD', op('MULTIPLY', sep.outputs[0], sep.outputs[0]), op('MULTIPLY', sep.outputs[1], sep.outputs[1])))
    # the log bends gently along its length: smooth, low-frequency warp only
    warp = N('ShaderNodeTexNoise'); warp.inputs['Scale'].default_value = 2.5; warp.inputs['Detail'].default_value = 1.0
    nt.links.new(tilt_m.outputs['Vector'], warp.inputs['Vector'])
    r = op('ADD', r, op('MULTIPLY', op('SUBTRACT', warp.outputs['Fac'], 0.5), warp_cm * 0.02))
    if irregular:
        # natural wood is never a clean ruler: wavy runs, a pinched year here, a bulge there
        wav = N('ShaderNodeTexNoise'); wav.inputs['Scale'].default_value = 14.0; wav.inputs['Detail'].default_value = 2.0
        wav.inputs['Roughness'].default_value = 0.55
        st = N('ShaderNodeMapping'); st.inputs['Scale'].default_value = (1.0, 1.0, 0.35)  # longer along the grain
        nt.links.new(tilt_m.outputs['Vector'], st.inputs['Vector']); nt.links.new(st.outputs['Vector'], wav.inputs['Vector'])
        r = op('ADD', r, op('MULTIPLY', op('SUBTRACT', wav.outputs['Fac'], 0.5), irregular * 0.006))
    # years of different widths: a smooth, always increasing function of the radius
    rr = op('MULTIPLY', r, per_m)
    def noise1(w, scale):
        n = N('ShaderNodeTexNoise'); n.noise_dimensions = '1D'; n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = 0.0
        nt.links.new(w, n.inputs['W'])
        return op('SUBTRACT', n.outputs['Fac'], 0.5)
    years = op('ADD', rr, op('MULTIPLY', noise1(rr, 0.13), 2.2 * (1 + irregular)))
    years = op('ADD', years, op('MULTIPLY', noise1(rr, 0.45), 0.8 * (1 + irregular)))
    # a few tenths of a millimetre of ragged edge
    jit = N('ShaderNodeTexNoise'); jit.inputs['Scale'].default_value = 600.0; jit.inputs['Detail'].default_value = 0.0
    nt.links.new(tilt_m.outputs['Vector'], jit.inputs['Vector'])
    years = op('ADD', years, op('MULTIPLY', op('SUBTRACT', jit.outputs['Fac'], 0.5), 0.08 / (1 + 2 * irregular)))
    ring = op('FRACT', years)
    ramp_n = nt.nodes.new('ShaderNodeValToRGB')
    cr = ramp_n.color_ramp
    cr.interpolation = 'EASE'
    cr.elements[0].position, cr.elements[0].color = ramp[0], srgb(light)
    cr.elements[1].position, cr.elements[1].color = ramp[1], srgb(light)
    e = cr.elements.new(ramp[2]); e.color = srgb(mid)
    e = cr.elements.new(ramp[3]); e.color = srgb(line)
    e = cr.elements.new(0.99); e.color = srgb(line)
    nt.links.new(ring, ramp_n.inputs['Fac'])
    # each year has its own strength: some lines bold, many faint
    wn = N('ShaderNodeTexWhiteNoise'); wn.noise_dimensions = '1D'
    nt.links.new(op('FLOOR', years), wn.inputs['W'])
    vr = N('ShaderNodeMapRange')
    vr.inputs['To Min'].default_value, vr.inputs['To Max'].default_value = line_var
    nt.links.new(op('POWER', wn.outputs['Value'], 0.7), vr.inputs['Value'])
    strength = nt.nodes.new('ShaderNodeMix'); strength.data_type = 'RGBA'
    strength.inputs['A'].default_value = srgb(light)
    nt.links.new(vr.outputs['Result'], strength.inputs['Factor'])
    nt.links.new(ramp_n.outputs['Color'], strength.inputs['B'])
    detail, detail_bw = ash_detail(nt)
    mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'
    mul.inputs['Factor'].default_value = 1.0
    comb = nt.nodes.new('ShaderNodeCombineColor')
    for k in ('Red', 'Green', 'Blue'):
        nt.links.new(detail, comb.inputs[k])
    nt.links.new(strength.outputs['Result'], mul.inputs['A'])
    nt.links.new(comb.outputs['Color'], mul.inputs['B'])
    nt.links.new(mul.outputs['Result'], bsdf.inputs['Base Color'])
    polish = GLOSS if name in ('wood', 'lip', 'lightWood', 'headWood') else 0.0
    bsdf.inputs['Roughness'].default_value = roughness * (1 - 0.3 * polish)
    if polish:
        # a thin satin coat: soft, broad highlights, never a mirror-like lacquer
        bsdf.inputs['Coat Weight'].default_value = 0.25 * polish
        bsdf.inputs['Coat Roughness'].default_value = 0.28
    bsdf.inputs['Specular IOR Level'].default_value = 0.35
    # fibres and pores give a faint relief
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.08; bump.inputs['Distance'].default_value = 0.0005
    nt.links.new(detail_bw, bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return m


def textured(name, tex, scale, roughness, sss=0.0, sss_radius=(1.0, 0.6, 0.4), tint=None, colour=None):
    m, nt, bsdf = new_mat(name)
    if tex:
        tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
        mp.inputs['Scale'].default_value = (scale, scale, scale)
        nt.links.new(tc.outputs['UV'], mp.inputs['Vector'])
        img = image(nt, tex); nt.links.new(mp.outputs['Vector'], img.inputs['Vector'])
        if tint:
            mix = nt.nodes.new('ShaderNodeMix'); mix.data_type = 'RGBA'; mix.blend_type = 'MULTIPLY'
            mix.inputs['Factor'].default_value = 1.0; mix.inputs['B'].default_value = srgb(tint)
            nt.links.new(img.outputs['Color'], mix.inputs['A'])
            nt.links.new(mix.outputs['Result'], bsdf.inputs['Base Color'])
        else:
            nt.links.new(img.outputs['Color'], bsdf.inputs['Base Color'])
    elif colour:
        bsdf.inputs['Base Color'].default_value = srgb(colour)
    bsdf.inputs['Roughness'].default_value = roughness
    if sss:
        bsdf.inputs['Subsurface Weight'].default_value = sss
        bsdf.inputs['Subsurface Radius'].default_value = sss_radius
        bsdf.inputs['Subsurface Scale'].default_value = 0.004
    return m, nt, bsdf


def skin_material():
    """Lamb skin: thin and translucent; light passes through into the dark bowl, so it reads
    darker in the middle and lighter at the edges, as on the reference photos."""
    m, nt, bsdf = textured('skin', WEB_TEX / 'skin_albedo.webp', 1 / 36, 0.65, tint='#fff6e8')
    out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    # (no subsurface: on a single thin sheet over the hollow it only loses light into the bowl)
    # the shared web texture is dark (mean ≈ 117 106 91); lift it to the cream-tan of the
    # reference skins (Cycles lets a colour factor exceed 1)
    src = bsdf.inputs['Base Color'].links[0].from_socket
    lift = nt.nodes.new('ShaderNodeMix'); lift.data_type = 'RGBA'; lift.blend_type = 'MULTIPLY'
    lift.inputs['Factor'].default_value = 1.0
    lift.inputs['B'].default_value = (1.95, 1.65, 1.2, 1.0)
    nt.links.new(src, lift.inputs['A']); nt.links.new(lift.outputs['Result'], bsdf.inputs['Base Color'])
    trans = nt.nodes.new('ShaderNodeBsdfTranslucent'); trans.inputs['Color'].default_value = srgb('#d9c4a8')
    mix = nt.nodes.new('ShaderNodeMixShader'); mix.inputs['Fac'].default_value = 0.06
    nt.links.new(bsdf.outputs['BSDF'], mix.inputs[1]); nt.links.new(trans.outputs['BSDF'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return m


def metal(name, colour, roughness):
    m, nt, bsdf = new_mat(name)
    bsdf.inputs['Base Color'].default_value = srgb(colour)
    bsdf.inputs['Metallic'].default_value = 1.0
    bsdf.inputs['Roughness'].default_value = roughness
    return m


def build_materials():
    # the scanned ash, turned 90° so its grain runs vertically (along the instrument) in box projection
    rot = ASSETS / 'ash_veneer_diff_2k_rot.jpg'
    if not rot.exists():
        from PIL import Image
        Image.open(ASSETS / 'ash_veneer_diff_2k.jpg').rotate(90, expand=True).save(rot, quality=95)
    mats = {
        # bowl: colours and log axis from revision round 5 (spec section 14), calibrated to R9/R10
        'wood': ring_wood('wood', *MULBERRY, (-8, -32), (0.22, 0.12), 1.6, 0.6, line_var=(0.55, 1.0)),
        'lip': ring_wood('lip', *(muted(c) for c in ('#8e6c52', '#7c5c44', '#5a4030')), (-8, -32), (0.22, 0.12), 1.6, 0.7, line_var=(0.2, 0.6)),
        # neck, head, pegs and fingerboard: quieter, close-grained woods (rings barely show)
        # neck and head: the same golden mulberry and satin finish as the bowl (user's request,
        # spec section 16), cut from the same log so the grain runs on along the instrument
        'lightWood': ring_wood('lightWood', *MULBERRY, (-8, -32), (0.22, 0.12), 1.6, 0.6, line_var=(0.55, 1.0)),
        # head: the flat faces of a far-off log axis cut the rings into straight, even bands;
        # a nearer, more tilted axis and strong irregularity give the arches, pinches and wavy
        # runs of real wood instead
        'headWood': ring_wood('headWood', *MULBERRY, (6, -10), (0.12, -0.07), 1.6, 0.6, warp_cm=1.0,
                              line_var=(0.45, 1.0), irregular=1.5),
        'pegWood': ring_wood('pegWood', '#6e4829', '#62401f', '#3e2612', (0, 0), (0, 0), 4.0, 0.5, warp_cm=0.2, line_var=(0.1, 0.4)),
        'boardWood': ring_wood('boardWood', '#4c2c17', '#42260f', '#2a170a', (0, -3), (0, 0), 3.0, 0.5, warp_cm=0.2, line_var=(0.2, 0.5)),
        'horn': textured('horn', None, 1, 0.35, sss=0.1, colour='#7a4a22')[0],
        'cavity': textured('cavity', None, 1, 0.95, colour='#150c07')[0],
        'skin': skin_material(),
        'bone': textured('bone', WEB_TEX / 'bone_albedo.webp', 1 / 6, 0.42, sss=0.2, tint='#d6c9ae')[0],
        'boneSmall': textured('boneSmall', WEB_TEX / 'bone_albedo.webp', 0.5, 0.42, sss=0.2, tint='#d6c9ae')[0],
        'inlay': textured('inlay', WEB_TEX / 'khatam.webp', 1 / 1.2, 0.45)[0],
        'gut': textured('gut', None, 1, 0.5, sss=0.3, sss_radius=(1.0, 0.8, 0.5), colour='#cfae6a')[0],
        'metal': metal('metal', '#d4d4d2', 0.28),
        'bronze': metal('bronze', '#b48848', 0.32),
        'stringSteel': metal('stringSteel', '#d4d4d2', 0.25),
        'stringBronze': metal('stringBronze', '#b48848', 0.3),
    }
    for o in bpy.context.scene.objects:
        if o.type != 'MESH':
            continue
        key = o.name.split('__')[-1].split('.')[0]
        o.data.materials.clear()
        o.data.materials.append(mats.get(key, mats['wood']))


# ---------------------------------------------------------------- light, backdrop, camera
def build_world(strength=1.0, rotation_deg=200):
    """Soft interior light from the HDRI for everything the instrument sees and reflects; the
    camera itself sees a dark backdrop (the user's choice)."""
    w = bpy.data.worlds.new('room'); bpy.context.scene.world = w
    w.use_nodes = True; nt = w.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Rotation'].default_value = (0, 0, math.radians(rotation_deg))
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(str(ASSETS / 'brown_photostudio_02_2k.hdr'))
    nt.links.new(tc.outputs['Generated'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], env.inputs['Vector'])
    room = nt.nodes.new('ShaderNodeBackground'); room.inputs['Strength'].default_value = strength
    nt.links.new(env.outputs['Color'], room.inputs['Color'])
    dark = nt.nodes.new('ShaderNodeBackground'); dark.inputs['Color'].default_value = srgb('#0b0a09'); dark.inputs['Strength'].default_value = 1.0
    lp = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    nt.links.new(room.outputs['Background'], mix.inputs[1]); nt.links.new(dark.outputs['Background'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])


def add_soft_key():
    """A large soft light from above and in front, like a big window or ceiling panel."""
    bpy.ops.object.light_add(type='AREA', location=(-0.9, -1.6, 1.9))
    key = bpy.context.object; key.name = 'key'
    key.data.shape = 'RECTANGLE'; key.data.size = 1.6; key.data.size_y = 1.0
    key.data.energy = 140; key.data.color = (1.0, 0.95, 0.88)
    direction = (PIVOT - key.location).normalized()
    key.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
    # a broad, dim fill from the camera side (a white wall behind the photographer), so faces
    # turned straight at the camera — the skin above all — are not left in the dark
    bpy.ops.object.light_add(type='AREA', location=(0.6, -3.2, 0.9))
    fill = bpy.context.object; fill.name = 'fill'
    fill.data.shape = 'RECTANGLE'; fill.data.size = 2.5; fill.data.size_y = 2.0
    fill.data.energy = 90; fill.data.color = (1.0, 0.96, 0.9)
    fill.rotation_euler = (PIVOT - fill.location).normalized().to_track_quat('-Z', 'Y').to_euler()
    return key


def add_window_light():
    """Natural, imperfect light, as in a photo taken by a window (round 8): one big window up
    and to the left whose frame casts soft bar shadows, a darker room, a warm bounce from a
    wooden table on the right, and a small back light that runs a little hot on the edges.
    The lights stay fixed while the instrument turns, so its light changes as a real one would."""
    target = PIVOT + Vector((0, 0, 0.05))
    def area(name, loc, size, size_y, energy, colour):
        bpy.ops.object.light_add(type='AREA', location=loc)
        l = bpy.context.object; l.name = name
        l.data.shape = 'RECTANGLE'; l.data.size = size; l.data.size_y = size_y
        l.data.energy = energy; l.data.color = colour
        l.rotation_euler = (target - l.location).normalized().to_track_quat('-Z', 'Y').to_euler()
        return l
    # Round 9: the window sits lower and more to the side, so faces turned up to the ceiling
    # while the instrument tips over (the skin above all) are not hit head-on; its glints on
    # the satin finish are toned down so they never burn a part of the instrument out.
    window = area('window', (-2.0, -0.8, 1.05), 1.1, 1.5, 230, (1.0, 0.93, 0.83))
    window.data.specular_factor = 0.55
    # the window frame: two crossing bars just in front of the glass, seen by the light only
    d = (target - window.location).normalized()
    for k, (sx, sy) in enumerate(((0.035, 1.6), (1.2, 0.035))):
        bpy.ops.mesh.primitive_plane_add(size=1, location=window.location + d * 0.12)
        bar = bpy.context.object; bar.name = f'window_bar{k}'
        bar.scale = (sx, sy, 1); bar.rotation_euler = window.rotation_euler
        bar.visible_camera = False; bar.visible_glossy = False
        # off-centre, as a real window never lines up with the subject
        bar.location += window.matrix_world.to_3x3() @ Vector((0.12, -0.18, 0))
    area('bounce', (1.4, -0.9, -0.35), 1.6, 1.0, 45, (1.0, 0.78, 0.55))
    # the back light: still a touch hot on the edges, but larger, dimmer and lower than in
    # round 8 — when the tar tips over backwards its upturned faces look straight into it,
    # and the small bright one burnt the skin and top out (measured: 1% of the instrument)
    rim = area('rim', (1.1, 1.6, 0.55), 0.8, 0.6, 75, (1.0, 0.9, 0.78))
    rim.data.specular_factor = 0.45
    # a black flag overhead, as photographers use: no light straight down onto upturned faces
    bpy.ops.mesh.primitive_plane_add(size=1, location=PIVOT + Vector((-0.2, 0, 1.6)))
    flag = bpy.context.object; flag.name = 'flag'; flag.scale = (2.2, 1.6, 1)
    flag.visible_camera = False; flag.visible_glossy = False
    return window


def add_camera():
    cam_data = bpy.data.cameras.new('camera')
    cam_data.sensor_fit = 'VERTICAL'
    cam_data.angle_y = math.radians(24)
    cam_data.clip_start = 0.05
    cam = bpy.data.objects.new('camera', cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    return cam


# ---------------------------------------------------------------- poses (same as the web page)
def pose_quaternion(yaw_deg, pitch_deg):
    """Web: q = Rx(pitch) · Ry(yaw). Web y is Blender z and web x is Blender x, so the same angles
    turn about Blender z (yaw) and x (pitch)."""
    qx = Quaternion((1, 0, 0), math.radians(pitch_deg))
    qz = Quaternion((0, 0, 1), math.radians(yaw_deg))
    return qx @ qz


def apply_pose(pivot, cam, yaw, pitch, target_web, dist_cm, elev_deg, aperture=0.0):
    pivot.rotation_mode = 'QUATERNION'
    q = pose_quaternion(yaw, pitch)
    pivot.rotation_quaternion = q
    # the look-at point is a spot on the instrument, so it turns with it
    t = PIVOT + q @ (web_to_blender(target_web) - PIVOT)
    e = math.radians(elev_deg)
    d = dist_cm * CM
    cam.location = t + Vector((0, -math.cos(e) * d, math.sin(e) * d))
    cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = (t - cam.location).length
    # the web aperture is tiny; map it to a photographic f-stop (close-ups get shallow focus)
    cam.data.dof.aperture_fstop = 5.6 if aperture > 0 else 16


def ease(t):
    u = min(1.0, max(0.0, (t - 0.15) / 0.7))
    return u * u * u * (u * (u * 6 - 15) + 10)


def sample_scroll(p):
    kf = SCENES['keyframes']
    i = 0
    while i < len(kf) - 2 and p > kf[i + 1]['at']:
        i += 1
    a, b = kf[i], kf[i + 1]
    t = ease((p - a['at']) / (b['at'] - a['at']))
    qa, qb = pose_quaternion(a['yaw'], a['pitch']), pose_quaternion(b['yaw'], b['pitch'])
    lerp = lambda x, y: x + (y - x) * t
    return {
        'q': qa.slerp(qb, t),
        'target': [lerp(x, y) for x, y in zip(a['target'], b['target'])],
        'dist': math.exp(lerp(math.log(a['dist']), math.log(b['dist']))),
        'elev': lerp(a['elev'], b['elev']),
        'exposure': lerp(a['exposure'], b['exposure']),
        'aperture': lerp(a.get('aperture', 0), b.get('aperture', 0)),
    }


def apply_state(pivot, cam, s):
    pivot.rotation_mode = 'QUATERNION'
    pivot.rotation_quaternion = s['q']
    t = PIVOT + s['q'] @ (web_to_blender(s['target']) - PIVOT)
    e = math.radians(s['elev']); d = s['dist'] * CM
    cam.location = t + Vector((0, -math.cos(e) * d, math.sin(e) * d))
    cam.rotation_euler = (t - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = (t - cam.location).length
    cam.data.dof.aperture_fstop = 16 - (16 - 5.6) * min(1.0, s['aperture'] / 0.0003)
    # the web page fades in from darkness at the start; exposure in stops
    bpy.context.scene.view_settings.exposure = math.log2(max(s['exposure'], 0.02))


# ---------------------------------------------------------------- main
def setup(width, height, samples):
    sc = reset()
    sc.render.resolution_x, sc.render.resolution_y = width, height
    sc.render.resolution_percentage = 100
    sc.cycles.samples = samples
    sc.render.image_settings.file_format = 'PNG'
    pivot, _ = import_model()
    build_materials()
    if os.environ.get('TAR_LIGHT', 'natural') == 'studio':
        build_world(); add_soft_key()  # rounds 1–7: soft, even studio light
    else:
        build_world(strength=0.25); add_window_light()
    cam = add_camera()
    return sc, pivot, cam


def render(sc, path, seed=0, raw_dir=None):
    """Renders one frame; unless TAR_FINISH=0, the photographic flaws of photo_finish.py are
    added and the untouched render is kept in raw_dir (or next to it, as *_raw.png)."""
    raw = (raw_dir / path.name) if raw_dir else path.with_name(path.stem + '_raw.png')
    raw.parent.mkdir(parents=True, exist_ok=True)
    sc.render.filepath = str(raw)
    t = time.time()
    bpy.ops.render.render(write_still=True)
    if os.environ.get('TAR_FINISH', '1') != '0':
        from PIL import Image
        import photo_finish
        photo_finish.finish(Image.open(raw), seed).save(path)
    else:
        raw.replace(path)
    print(f'rendered {path.name} in {time.time() - t:.1f}s', flush=True)


def main(argv):
    mode = argv[0] if argv else 'test'
    if mode == 'test':
        sc, pivot, cam = setup(960, 540, 48)
        out = BUILD / os.environ.get('TAR_TEST_DIR', 'test'); out.mkdir(parents=True, exist_ok=True)
        for k in SCENES['keyframes'][1:]:
            apply_pose(pivot, cam, k['yaw'], k['pitch'], k['target'], k['dist'], k['elev'], k.get('aperture', 0))
            render(sc, out / f"scene_{k['caption']}.png", seed=k['caption'], raw_dir=out / 'raw')
    elif mode == 'fall':
        # the instrument tipping over backwards (pitch down to -90°), straight on and turned,
        # to check the window light never burns parts of it out (round 9)
        sc, pivot, cam = setup(960, 540, 32)
        out = BUILD / os.environ.get('TAR_TEST_DIR', 'fall'); out.mkdir(parents=True, exist_ok=True)
        c = SCENES['pivot']
        for yaw in (0, -35, -90, 180):
            for pitch in (0, -30, -60, -75, -90):
                apply_pose(pivot, cam, yaw, pitch, [c['x'], c['y'], c['z']], 250, 0)
                render(sc, out / f'y{yaw:+04d}_p{pitch:+03d}.png', seed=(yaw + 360) * 100 + pitch + 100, raw_dir=out / 'raw')
    elif mode == 'scroll':
        start, end = int(argv[1]), int(argv[2])
        total = int(argv[3]) if len(argv) > 3 else 240
        sc, pivot, cam = setup(1600, 900, 96)
        out = HERE / 'frames_raw' / 'scroll'; out.mkdir(parents=True, exist_ok=True)
        for f in range(start, end + 1):
            path = out / f'{f:04d}.png'
            if path.exists():
                continue  # resumable: frames already rendered are kept
            apply_state(pivot, cam, sample_scroll(f / (total - 1)))
            render(sc, path, seed=f, raw_dir=HERE / 'frames_raw' / 'scroll_raw')
    elif mode == 'sheet':
        sc, pivot, cam = setup(1200, 900, 64)
        out = HERE / 'frames_raw' / 'sheet'; out.mkdir(parents=True, exist_ok=True)
        c = SCENES['pivot']
        for pitch in (-60, -30, 0, 30, 60):
            for yaw in range(0, 360, 15):
                path = out / f'y{yaw:03d}_p{pitch:+03d}.png'
                if path.exists():
                    continue
                apply_pose(pivot, cam, yaw, pitch, [c['x'], c['y'], c['z']], 250, 0)
                render(sc, path, seed=10000 + yaw * 10 + pitch, raw_dir=HERE / 'frames_raw' / 'sheet_raw')


if __name__ == '__main__':
    main(sys.argv[1:])
