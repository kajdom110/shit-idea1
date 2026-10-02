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
              ramp=(0.0, 0.38, 0.74, 0.92), line_var=(0.3, 1.0), irregular=0.0):
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
    jit = N('ShaderNodeTexNoise'); jit.inputs['Scale'].default_value = 250.0; jit.inputs['Detail'].default_value = 0.0
    nt.links.new(tilt_m.outputs['Vector'], jit.inputs['Vector'])
    years = op('ADD', years, op('MULTIPLY', op('SUBTRACT', jit.outputs['Fac'], 0.5), 0.012 / (1 + 2 * irregular)))
    ring = op('FRACT', years)
    ramp_n = nt.nodes.new('ShaderNodeValToRGB')
    cr = ramp_n.color_ramp
    cr.interpolation = 'EASE'
    cr.elements[0].position, cr.elements[0].color = ramp[0], srgb(light)
    # no flat plateau of earlywood: the tone keeps darkening a little through the year, so a
    # flat face cutting the rings at a shallow angle shows soft gradients, not terraces (round 11)
    cr.elements[1].position, cr.elements[1].color = ramp[1], tuple(a + (b - a) * 0.3 for a, b in zip(srgb(light), srgb(mid)))
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
    # Close-up detail (round 11). Where a flat face cuts the rings at a shallow angle each
    # year turns into a broad, empty band; real wood fills it with fine pore streaks that
    # follow the rings, and with fibre lines running along the grain.
    pn = N('ShaderNodeTexNoise'); pn.inputs['Scale'].default_value = 300.0; pn.inputs['Detail'].default_value = 1.0
    nt.links.new(tilt_m.outputs['Vector'], pn.inputs['Vector'])
    phase = op('ADD', op('MULTIPLY', years, 3.0), op('MULTIPLY', pn.outputs['Fac'], 0.8))
    streak = op('SINE', op('MULTIPLY', phase, 2 * math.pi))
    fine_f = op('ADD', 1.0, op('MULTIPLY', streak, 0.09))
    fib_map = N('ShaderNodeMapping'); fib_map.inputs['Scale'].default_value = (900.0, 900.0, 12.0)
    nt.links.new(tilt_m.outputs['Vector'], fib_map.inputs['Vector'])
    fib = N('ShaderNodeTexNoise'); fib.inputs['Scale'].default_value = 1.0; fib.inputs['Detail'].default_value = 3.0
    fib.inputs['Roughness'].default_value = 0.6
    nt.links.new(fib_map.outputs['Vector'], fib.inputs['Vector'])
    fib_f = op('ADD', 1.0, op('MULTIPLY', op('SUBTRACT', fib.outputs['Fac'], 0.5), 0.3))
    close_f = op('MULTIPLY', fine_f, fib_f)
    close_c = N('ShaderNodeCombineColor')
    for k in ('Red', 'Green', 'Blue'):
        nt.links.new(close_f, close_c.inputs[k])
    closemul = N('ShaderNodeMix'); closemul.data_type = 'RGBA'; closemul.blend_type = 'MULTIPLY'
    closemul.inputs['Factor'].default_value = 1.0
    nt.links.new(strength.outputs['Result'], closemul.inputs['A']); nt.links.new(close_c.outputs['Color'], closemul.inputs['B'])
    detail, detail_bw = ash_detail(nt)
    mul = nt.nodes.new('ShaderNodeMix'); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'
    mul.inputs['Factor'].default_value = 1.0
    comb = nt.nodes.new('ShaderNodeCombineColor')
    for k in ('Red', 'Green', 'Blue'):
        nt.links.new(detail, comb.inputs[k])
    nt.links.new(closemul.outputs['Result'], mul.inputs['A'])
    nt.links.new(comb.outputs['Color'], mul.inputs['B'])
    nt.links.new(mul.outputs['Result'], bsdf.inputs['Base Color'])
    polish = GLOSS if name in ('wood', 'woodTop', 'lightWood', 'headWood') else 0.0
    bsdf.inputs['Roughness'].default_value = roughness * (1 - 0.3 * polish)
    if polish:
        # a thin satin coat: soft, broad highlights, never a mirror-like lacquer
        bsdf.inputs['Coat Weight'].default_value = 0.25 * polish
        bsdf.inputs['Coat Roughness'].default_value = 0.28
    bsdf.inputs['Specular IOR Level'].default_value = 0.35
    # fibres and pores give a faint relief
    bump = nt.nodes.new('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.08; bump.inputs['Distance'].default_value = 0.0005
    height = op('ADD', detail_bw, op('MULTIPLY', fib.outputs['Fac'], 0.6))
    nt.links.new(height, bump.inputs['Height'])
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


SKIN_EDGE = None  # (image path, x0, z0, width, height) in metres, made in setup()


def make_skin_edge_map(objs, px_per_cm=20, max_cm=3.0):
    """Distance from the skin's glued edge, as an image over the skin (0 at the edge, white
    3 cm in). Real skin reads lighter and warmer near the edge, where it lies on wood and is
    soaked with glue, and darker in the middle, where the dark hollow shows through it."""
    from PIL import Image, ImageDraw, ImageFilter
    skin = [o for o in objs if o.name.startswith('skin__')][0]
    me = skin.data
    xs = [v.co.x for v in me.vertices]; zs = [v.co.z for v in me.vertices]
    x0, z0 = min(xs) - 0.005, min(zs) - 0.005
    w, h = max(xs) + 0.005 - x0, max(zs) + 0.005 - z0
    W, H = round(w * 100 * px_per_cm), round(h * 100 * px_per_cm)
    im = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(im)
    to_px = lambda v: ((v.co.x - x0) / w * W, (1 - (v.co.z - z0) / h) * H)
    for poly in me.polygons:
        dr.polygon([to_px(me.vertices[i]) for i in poly.vertices], fill=255)
    steps = round(max_cm * px_per_cm)
    dist = Image.new('L', (W, H), 0)
    cur = im
    for k in range(steps):  # erode one pixel at a time: each survivor is one step further in
        cur = cur.filter(ImageFilter.MinFilter(3))
        lvl = round(255 * (k + 1) / steps)
        dist.paste(lvl, mask=cur)
    dist = dist.filter(ImageFilter.GaussianBlur(1.5))
    path = BUILD / 'skin_edge.png'; dist.save(path)
    return (path, x0, z0, w, h)


def skin_material():
    """Lamb skin: thin, translucent rawhide. The web texture gives the broad tone; for close-ups
    (round 11) it gains what real stretched skin shows: soft mottling where it is thicker or
    thinner, a faint network of veins and fibres, sparse follicle specks and a fine relief."""
    m, nt, bsdf = textured('skin', WEB_TEX / 'skin_albedo.webp', 1 / 36, 0.65, tint='#fff6e8')
    out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    N = nt.nodes.new
    def op(kind, x, y=None):
        n = N('ShaderNodeMath'); n.operation = kind
        for i, v in enumerate((x, y)):
            if v is None: continue
            if isinstance(v, (int, float)): n.inputs[i].default_value = v
            else: nt.links.new(v, n.inputs[i])
        return n.outputs[0]
    def grey(f):
        c = N('ShaderNodeCombineColor')
        for k in ('Red', 'Green', 'Blue'): nt.links.new(f, c.inputs[k])
        return c.outputs['Color']
    def multiply(a_sock, b_sock):
        mx = N('ShaderNodeMix'); mx.data_type = 'RGBA'; mx.blend_type = 'MULTIPLY'; mx.inputs['Factor'].default_value = 1.0
        nt.links.new(a_sock, mx.inputs['A']); nt.links.new(b_sock, mx.inputs['B'])
        return mx.outputs['Result']
    # (no subsurface: on a single thin sheet over the hollow it only loses light into the bowl)
    # the shared web texture is dark (mean ≈ 117 106 91); lift it to the cream-tan of the
    # reference skins (Cycles lets a colour factor exceed 1)
    src = bsdf.inputs['Base Color'].links[0].from_socket
    lift = N('ShaderNodeMix'); lift.data_type = 'RGBA'; lift.blend_type = 'MULTIPLY'
    lift.inputs['Factor'].default_value = 1.0
    lift.inputs['B'].default_value = (1.95, 1.65, 1.2, 1.0)
    nt.links.new(src, lift.inputs['A'])
    co = N('ShaderNodeTexCoord').outputs['Object']
    # thicker and thinner patches, a few cm across, a little warmer where thicker
    mott = N('ShaderNodeTexNoise'); mott.inputs['Scale'].default_value = 22.0; mott.inputs['Detail'].default_value = 4.0
    mott.inputs['Roughness'].default_value = 0.55
    nt.links.new(co, mott.inputs['Vector'])
    thick = mott.outputs['Fac']
    tone = op('ADD', 0.93, op('MULTIPLY', thick, 0.14))
    warm = N('ShaderNodeMix'); warm.data_type = 'RGBA'
    warm.inputs['A'].default_value = (0.97, 0.98, 1.0, 1); warm.inputs['B'].default_value = (1.03, 0.99, 0.93, 1)
    nt.links.new(thick, warm.inputs['Factor'])
    col = multiply(multiply(lift.outputs['Result'], grey(tone)), warm.outputs['Result'])
    # veins and fibres: cell edges of a warped Voronoi, at two sizes, very low contrast
    warp = N('ShaderNodeTexNoise'); warp.inputs['Scale'].default_value = 60.0
    nt.links.new(co, warp.inputs['Vector'])
    wv = N('ShaderNodeVectorMath'); wv.operation = 'SCALE'; wv.inputs['Scale'].default_value = 0.004
    nt.links.new(warp.outputs['Color'], wv.inputs[0])
    wco = N('ShaderNodeVectorMath'); wco.operation = 'ADD'
    nt.links.new(co, wco.inputs[0]); nt.links.new(wv.outputs[0], wco.inputs[1])
    vein_h = None
    for scale, width, depth in ((45.0, 0.035, 0.05), (160.0, 0.05, 0.035)):
        vo = N('ShaderNodeTexVoronoi'); vo.feature = 'DISTANCE_TO_EDGE'; vo.inputs['Scale'].default_value = scale
        nt.links.new(wco.outputs[0], vo.inputs['Vector'])
        line = op('SUBTRACT', 1.0, op('MINIMUM', op('DIVIDE', vo.outputs['Distance'], width), 1.0))
        col = multiply(col, grey(op('SUBTRACT', 1.0, op('MULTIPLY', line, depth))))
        vein_h = line if vein_h is None else op('ADD', vein_h, line)
    # sparse follicle specks
    sp = N('ShaderNodeTexVoronoi'); sp.inputs['Scale'].default_value = 700.0
    nt.links.new(co, sp.inputs['Vector'])
    dot = op('SUBTRACT', 1.0, op('MINIMUM', op('DIVIDE', sp.outputs['Distance'], 0.12), 1.0))
    sep = N('ShaderNodeSeparateColor')
    nt.links.new(sp.outputs['Color'], sep.inputs['Color'])
    keep = op('GREATER_THAN', sep.outputs['Red'], 0.82)
    speck = op('MULTIPLY', dot, keep)
    col = multiply(col, grey(op('SUBTRACT', 1.0, op('MULTIPLY', speck, 0.25))))
    # Round 12: the skin over the hollow vs over the wood. In the middle the dark bowl shows
    # through the thin skin: it reads greyer, cooler and darker (R7: about 69 65 75). Near the
    # edge it lies on the wooden lip and is soaked with glue: lighter, warmer, more opaque, with a
    # thin darker line right at the glued edge.
    path, ex0, ez0, ew, eh = SKIN_EDGE
    sepc = N('ShaderNodeSeparateXYZ'); nt.links.new(co, sepc.inputs[0])
    uvc = N('ShaderNodeCombineXYZ')
    nt.links.new(op('DIVIDE', op('SUBTRACT', sepc.outputs['X'], ex0), ew), uvc.inputs['X'])
    nt.links.new(op('DIVIDE', op('SUBTRACT', sepc.outputs['Z'], ez0), eh), uvc.inputs['Y'])
    edge_img = N('ShaderNodeTexImage'); edge_img.image = bpy.data.images.load(str(path), check_existing=False)
    edge_img.image.colorspace_settings.name = 'Non-Color'; edge_img.extension = 'EXTEND'
    nt.links.new(uvc.outputs[0], edge_img.inputs['Vector'])
    inward = edge_img.outputs['Color']  # 0 at the edge … 1 three cm in (grey: the R channel is enough)
    inw = N('ShaderNodeSeparateColor'); nt.links.new(inward, inw.inputs['Color'])
    d = inw.outputs['Red']
    hollow = N('ShaderNodeMapRange'); hollow.inputs['From Min'].default_value = 0.15; hollow.inputs['From Max'].default_value = 0.85
    hollow.interpolation_type = 'SMOOTHSTEP'
    nt.links.new(d, hollow.inputs['Value'])
    hol = hollow.outputs['Result']
    # break the edge band up so it is not a ruled stripe: glue never spreads evenly
    gl = N('ShaderNodeTexNoise'); gl.inputs['Scale'].default_value = 40.0; gl.inputs['Detail'].default_value = 3.0
    nt.links.new(co, gl.inputs['Vector'])
    hol = op('MINIMUM', 1.0, op('MAXIMUM', 0.0, op('ADD', op('MULTIPLY', hol, 0.85), op('MULTIPLY', op('SUBTRACT', gl.outputs['Fac'], 0.5), 0.7))))
    over = N('ShaderNodeMix'); over.data_type = 'RGBA'
    over.inputs['A'].default_value = (1.06, 0.98, 0.86, 1)   # over the wood, glued: warm, light
    over.inputs['B'].default_value = (0.7, 0.69, 0.73, 1)   # over the hollow: grey-violet, darker
    nt.links.new(hol, over.inputs['Factor'])
    col = multiply(col, over.outputs['Result'])
    # the hollow behind takes the colour out of the thin skin: greyer, a touch violet, not brown
    bw = N('ShaderNodeRGBToBW'); nt.links.new(col, bw.inputs['Color'])
    desat = N('ShaderNodeMix'); desat.data_type = 'RGBA'
    nt.links.new(op('MULTIPLY', hol, 0.5), desat.inputs['Factor'])
    nt.links.new(col, desat.inputs['A'])
    nt.links.new(multiply(grey(bw.outputs['Val']), N('ShaderNodeRGB').outputs[0]), desat.inputs['B'])
    rgbn = [n for n in nt.nodes if n.type == 'RGB'][-1]; rgbn.outputs[0].default_value = (0.97, 0.95, 1.06, 1)
    col = desat.outputs['Result']
    glue = N('ShaderNodeMapRange'); glue.inputs['From Min'].default_value = 0.0; glue.inputs['From Max'].default_value = 0.08
    glue.inputs['To Min'].default_value = 0.72; glue.inputs['To Max'].default_value = 1.0
    nt.links.new(d, glue.inputs['Value'])
    glue_c = N('ShaderNodeCombineColor')
    nt.links.new(glue.outputs['Result'], glue_c.inputs['Red'])
    nt.links.new(op('ADD', 0.03, op('MULTIPLY', glue.outputs['Result'], 0.97)), glue_c.inputs['Green'])
    nt.links.new(op('ADD', 0.08, op('MULTIPLY', glue.outputs['Result'], 0.92)), glue_c.inputs['Blue'])
    col = multiply(col, glue_c.outputs['Color'])
    nt.links.new(col, bsdf.inputs['Base Color'])
    # fine relief: raised veins, a faint grain, and the specks as tiny pits
    micro = N('ShaderNodeTexNoise'); micro.inputs['Scale'].default_value = 2500.0; micro.inputs['Detail'].default_value = 2.0
    nt.links.new(co, micro.inputs['Vector'])
    height = op('ADD', op('MULTIPLY', vein_h, 0.5), op('SUBTRACT', micro.outputs['Fac'], op('MULTIPLY', speck, 0.6)))
    bump = N('ShaderNodeBump'); bump.inputs['Strength'].default_value = 0.12; bump.inputs['Distance'].default_value = 0.0003
    nt.links.new(height, bump.inputs['Height']); nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
    # light shows through more where the skin is thinner
    trans = N('ShaderNodeBsdfTranslucent'); trans.inputs['Color'].default_value = srgb('#d9c4a8')
    mix = N('ShaderNodeMixShader')
    nt.links.new(op('MULTIPLY', hol, op('SUBTRACT', 0.35, op('MULTIPLY', thick, 0.15))), mix.inputs['Fac'])
    # the glued edge has a soft sheen of dried glue; the free skin is matte
    rough = N('ShaderNodeMapRange'); rough.inputs['To Min'].default_value = 0.45; rough.inputs['To Max'].default_value = 0.68
    nt.links.new(hol, rough.inputs['Value']); nt.links.new(rough.outputs['Result'], bsdf.inputs['Roughness'])
    nt.links.new(bsdf.outputs['BSDF'], mix.inputs[1]); nt.links.new(trans.outputs['BSDF'], mix.inputs[2])
    nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    return m


def metal(name, colour, roughness):
    m, nt, bsdf = new_mat(name)
    bsdf.inputs['Base Color'].default_value = srgb(colour)
    bsdf.inputs['Metallic'].default_value = 1.0
    bsdf.inputs['Roughness'].default_value = roughness
    return m


# ---------------------------------------------------------------- round 13: the user's samples
# Materials rebuilt from the two sample sheets the user chose (docs/tar-3d/refs-chatgpt): dark,
# glossy red-brown wood with long flame streaks and thin pale inlay lines along the bowls, a pale
# maple neck, grey-brown marbled skin and a khatam border round it, on a charcoal studio sweep.
class Nodes:
    """Small helper for building node graphs."""
    def __init__(self, nt):
        self.nt = nt

    def new(self, kind, **inputs):
        n = self.nt.nodes.new(kind)
        for k, v in inputs.items():
            n.inputs[k].default_value = v
        return n

    def link(self, a, b):
        self.nt.links.new(a, b)

    def op(self, kind, x, y=None, z=None):
        n = self.nt.nodes.new('ShaderNodeMath'); n.operation = kind
        for i, v in enumerate((x, y, z)):
            if v is None: continue
            if isinstance(v, (int, float)): n.inputs[i].default_value = v
            else: self.nt.links.new(v, n.inputs[i])
        return n.outputs[0]

    def grey(self, f):
        c = self.nt.nodes.new('ShaderNodeCombineColor')
        for k in ('Red', 'Green', 'Blue'): self.nt.links.new(f, c.inputs[k])
        return c.outputs['Color']

    def mix(self, fac, a, b, blend='MIX'):
        m = self.nt.nodes.new('ShaderNodeMix'); m.data_type = 'RGBA'; m.blend_type = blend
        for sock, v in (('Factor', fac), ('A', a), ('B', b)):
            if isinstance(v, (int, float)): m.inputs[sock].default_value = v
            elif isinstance(v, tuple): m.inputs[sock].default_value = v
            else: self.nt.links.new(v, m.inputs[sock])
        return m.outputs['Result']

    def noise(self, vec, scale, detail=2.0, rough=0.5, distortion=0.0, stretch=None):
        if stretch:
            mp = self.new('ShaderNodeMapping'); mp.inputs['Scale'].default_value = stretch
            self.link(vec, mp.inputs['Vector']); vec = mp.outputs['Vector']
        n = self.new('ShaderNodeTexNoise', Scale=scale, Detail=detail, Roughness=rough, Distortion=distortion)
        self.link(vec, n.inputs['Vector'])
        return n

    def ramp(self, fac, stops):
        r = self.nt.nodes.new('ShaderNodeValToRGB'); cr = r.color_ramp
        cr.elements[0].position, cr.elements[0].color = stops[0][0], srgb(stops[0][1])
        cr.elements[1].position, cr.elements[1].color = stops[-1][0], srgb(stops[-1][1])
        for pos, col in stops[1:-1]:
            e = cr.elements.new(pos); e.color = srgb(col)
        self.link(fac, r.inputs['Fac'])
        return r.outputs['Color']


ROSEWOOD = ('#0e0301', '#2e0b02', '#581a06', '#8c3410')  # deep, dark, mid, light (sample: mean 73 32 18)


def rosewood(name, tones=ROSEWOOD, gloss=1.0, stripes=0, stripe_axis_y=0.0, stripe_top=1.0, scale=1.0, spec=0.5, rough=0.42):
    """Dark red-brown wood with long, wavy flame streaks along the instrument (Blender z) and a
    deep, glossy lacquer. stripes>0 adds that many thin pale inlay lines round the bowl's long
    axis (one down the middle of the back), as on the samples."""
    m, nt, bsdf = new_mat(name); g = Nodes(nt)
    co = g.new('ShaderNodeTexCoord').outputs['Object']
    # broad light and dark areas, long along the grain
    broad = g.noise(co, 1.0, detail=2, rough=0.5, distortion=0.3, stretch=(7 * scale, 7 * scale, 0.9 * scale))
    # the flame: tight wavy streaks, stretched along the grain and bent by the broad noise
    warp = g.new('ShaderNodeVectorMath'); warp.operation = 'ADD'
    wsc = g.new('ShaderNodeVectorMath'); wsc.operation = 'SCALE'; wsc.inputs['Scale'].default_value = 0.02
    g.link(broad.outputs['Color'], wsc.inputs[0]); g.link(co, warp.inputs[0]); g.link(wsc.outputs[0], warp.inputs[1])
    # (octaves of a noise grow finer along every axis alike, so each scale gets its own
    # stretched noise: that keeps all of them long along the grain instead of mottled)
    flame = g.noise(warp.outputs[0], 1.0, detail=1, rough=0.5, stretch=(110 * scale, 110 * scale, 1.2 * scale))
    flame2 = g.noise(warp.outputs[0], 1.0, detail=1, rough=0.5, stretch=(380 * scale, 380 * scale, 3.0 * scale))
    tone = g.op('ADD', g.op('MULTIPLY', flame.outputs['Fac'], 0.6), g.op('MULTIPLY', flame2.outputs['Fac'], 0.3))
    tone = g.op('ADD', tone, g.op('MULTIPLY', broad.outputs['Fac'], 0.3))
    tone = g.op('SUBTRACT', tone, 0.1)
    col = g.ramp(tone, [(0.22, tones[0]), (0.4, tones[1]), (0.56, tones[2]), (0.72, tones[3])])
    # fine fibres and pores
    fib = g.noise(co, 1.0, detail=3, rough=0.6, stretch=(1200, 1200, 20))
    col = g.mix(1.0, col, g.grey(g.op('ADD', 0.88, g.op('MULTIPLY', fib.outputs['Fac'], 0.24))), 'MULTIPLY')
    if stripes:
        sep = g.new('ShaderNodeSeparateXYZ'); g.link(co, sep.inputs[0])
        theta = g.op('ARCTAN2', sep.outputs['X'], g.op('SUBTRACT', sep.outputs['Y'], stripe_axis_y))
        f = g.op('FRACT', g.op('ADD', g.op('MULTIPLY', theta, stripes / (2 * math.pi)), 0.5))
        dist = g.op('ABSOLUTE', g.op('SUBTRACT', f, 0.5))  # 0 on a line … 0.5 between lines
        line = g.op('SUBTRACT', 1.0, g.op('SMOOTH_MIN', g.op('DIVIDE', dist, 0.006), 1.0, 0.2))
        line = g.op('MAXIMUM', 0.0, g.op('MINIMUM', 1.0, line))
        line = g.op('MULTIPLY', line, g.op('MINIMUM', 1.0, g.op('MAXIMUM', 0.0, g.op('DIVIDE', g.op('SUBTRACT', stripe_top, sep.outputs['Z']), 0.04))))
        rad = g.op('SQRT', g.op('ADD', g.op('POWER', sep.outputs['X'], 2.0), g.op('POWER', g.op('SUBTRACT', sep.outputs['Y'], stripe_axis_y), 2.0)))
        line = g.op('MULTIPLY', line, g.op('MINIMUM', 1.0, g.op('MAXIMUM', 0.0, g.op('DIVIDE', g.op('SUBTRACT', rad, 0.03), 0.03))))
        col = g.mix(line, col, srgb('#dcc08e'))
    g.link(col, bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = rough
    bsdf.inputs['Specular IOR Level'].default_value = spec
    bsdf.inputs['Coat Weight'].default_value = gloss
    bsdf.inputs['Coat Roughness'].default_value = 0.11
    bsdf.inputs['Coat IOR'].default_value = 1.5
    bump = g.new('ShaderNodeBump', Strength=0.04, Distance=0.0004)
    g.link(fib.outputs['Fac'], bump.inputs['Height']); g.link(bump.outputs['Normal'], bsdf.inputs['Normal'])
    return m


def maple(name, base='#e2c79a', streak='#c9a46e', gloss=0.35):
    """Pale, close-grained neck wood (the samples' neck is cream with faint streaks)."""
    m, nt, bsdf = new_mat(name); g = Nodes(nt)
    co = g.new('ShaderNodeTexCoord').outputs['Object']
    st = g.noise(co, 1.0, detail=4, rough=0.6, stretch=(400, 400, 8))
    col = g.ramp(st.outputs['Fac'], [(0.3, base), (0.75, streak)])
    g.link(col, bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.45
    bsdf.inputs['Coat Weight'].default_value = gloss; bsdf.inputs['Coat Roughness'].default_value = 0.2
    return m


def mesh_edge_map(objs, prefix, name, px_per_cm=20, max_cm=3.0):
    """Distance from the edge of a flat part (in the front plane), as an image; see make_skin_edge_map."""
    from PIL import Image, ImageDraw, ImageFilter
    ob = [o for o in objs if o.name.startswith(prefix)][0]; me = ob.data
    xs = [v.co.x for v in me.vertices]; zs = [v.co.z for v in me.vertices]
    x0, z0 = min(xs) - 0.005, min(zs) - 0.005
    w, h = max(xs) + 0.005 - x0, max(zs) + 0.005 - z0
    W, H = round(w * 100 * px_per_cm), round(h * 100 * px_per_cm)
    im = Image.new('L', (W, H), 0); dr = ImageDraw.Draw(im)
    to_px = lambda v: ((v.co.x - x0) / w * W, (1 - (v.co.z - z0) / h) * H)
    front = max(v.co.y for v in me.vertices)
    for poly in me.polygons:
        if abs(poly.normal.y) > 0.5:  # faces in the front plane only
            dr.polygon([to_px(me.vertices[i]) for i in poly.vertices], fill=255)
    steps = round(max_cm * px_per_cm); dist = Image.new('L', (W, H), 0); cur = im
    for k in range(steps):
        cur = cur.filter(ImageFilter.MinFilter(3))
        dist.paste(round(255 * (k + 1) / steps), mask=cur)
    dist = dist.filter(ImageFilter.GaussianBlur(1.0))
    path = BUILD / f'{name}_edge.png'; dist.save(path)
    return (path, x0, z0, w, h, max_cm)


LIP_EDGE = None


def edge_value(g, co, edge):
    path, x0, z0, w, h = edge[:5]
    sep = g.new('ShaderNodeSeparateXYZ'); g.link(co, sep.inputs[0])
    uv = g.new('ShaderNodeCombineXYZ')
    g.link(g.op('DIVIDE', g.op('SUBTRACT', sep.outputs['X'], x0), w), uv.inputs['X'])
    g.link(g.op('DIVIDE', g.op('SUBTRACT', sep.outputs['Z'], z0), h), uv.inputs['Y'])
    img = g.new('ShaderNodeTexImage'); img.image = bpy.data.images.load(str(path), check_existing=False)
    img.image.colorspace_settings.name = 'Non-Color'; img.extension = 'EXTEND'
    g.link(uv.outputs[0], img.inputs['Vector'])
    return img.outputs['Color'], sep


def khatam_lip():
    """The border round the skin: a pale line on each side and, between them, a dark band of
    small pale triangles pointing in (khatam), as on the samples."""
    m, nt, bsdf = new_mat('lip'); g = Nodes(nt)
    co = g.new('ShaderNodeTexCoord').outputs['Object']
    ev, sep = edge_value(g, co, LIP_EDGE)
    sc = g.new('ShaderNodeSeparateColor'); g.link(ev, sc.inputs['Color'])
    d_cm = g.op('MULTIPLY', sc.outputs['Red'], LIP_EDGE[5])       # cm from the nearest edge
    half = 0.95                                                   # the border is about 1.9 cm wide
    across = g.op('MINIMUM', 1.0, g.op('DIVIDE', d_cm, half))     # 0 at an edge … 1 in the middle
    pale = g.op('LESS_THAN', d_cm, 0.06)                          # the two pale lines
    # along the band: a coordinate that keeps running round both curves of the outline
    along = g.op('ADD', g.op('MULTIPLY', sep.outputs['X'], 260.0), g.op('MULTIPLY', sep.outputs['Z'], 260.0))
    tri = g.op('MULTIPLY', g.op('ABSOLUTE', g.op('SUBTRACT', g.op('FRACT', along), 0.5)), 2.0)
    # small triangles: at a distance the band must read dark with a fine pale pattern
    tooth = g.op('LESS_THAN', g.op('DIVIDE', g.op('SUBTRACT', across, 0.3), 0.35), g.op('MULTIPLY', tri, 0.8))
    tooth = g.op('MULTIPLY', tooth, g.op('MULTIPLY', g.op('GREATER_THAN', across, 0.3), g.op('LESS_THAN', across, 0.62)))
    col = g.mix(tooth, srgb('#160b06'), srgb('#bfae8c'))
    col = g.mix(pale, col, srgb('#b08f5e'))
    g.link(col, bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.35
    bsdf.inputs['Coat Weight'].default_value = 0.8; bsdf.inputs['Coat Roughness'].default_value = 0.1
    return m


def parchment_skin():
    """The samples' skin: grey-brown, matte, marbled with fine darker and lighter veins, a little
    darker towards its glued edge."""
    m, nt, bsdf = new_mat('skin'); g = Nodes(nt)
    co = g.new('ShaderNodeTexCoord').outputs['Object']
    marble = g.noise(co, 90.0, detail=10, rough=0.66, distortion=2.0)
    base = g.ramp(marble.outputs['Fac'], [(0.3, '#4a4038'), (0.5, '#6a5f54'), (0.7, '#857767')])
    # fine dark veins (cell edges of a warped Voronoi) and a lighter network between them
    wv = g.new('ShaderNodeVectorMath'); wv.operation = 'SCALE'; wv.inputs['Scale'].default_value = 0.003
    g.link(marble.outputs['Color'], wv.inputs[0])
    wco = g.new('ShaderNodeVectorMath'); wco.operation = 'ADD'; g.link(co, wco.inputs[0]); g.link(wv.outputs[0], wco.inputs[1])
    col = base
    for scale, width, depth in ((90.0, 0.04, 0.25), (320.0, 0.05, 0.2)):
        vo = g.new('ShaderNodeTexVoronoi', Scale=scale); vo.feature = 'DISTANCE_TO_EDGE'
        g.link(wco.outputs[0], vo.inputs['Vector'])
        line = g.op('SUBTRACT', 1.0, g.op('MINIMUM', g.op('DIVIDE', vo.outputs['Distance'], width), 1.0))
        col = g.mix(1.0, col, g.grey(g.op('SUBTRACT', 1.0, g.op('MULTIPLY', line, depth))), 'MULTIPLY')
    # darker where it is glued down at the edge
    ev, _ = edge_value(g, co, SKIN_EDGE)
    sc = g.new('ShaderNodeSeparateColor'); g.link(ev, sc.inputs['Color'])
    edge = g.op('SUBTRACT', 1.0, g.op('MINIMUM', 1.0, g.op('DIVIDE', sc.outputs['Red'], 0.25)))
    col = g.mix(g.op('MULTIPLY', edge, 0.45), col, srgb('#3d3128'))
    g.link(col, bsdf.inputs['Base Color'])
    micro = g.noise(co, 2500.0, detail=2)
    h = g.op('ADD', micro.outputs['Fac'], g.op('MULTIPLY', marble.outputs['Fac'], 0.5))
    bump = g.new('ShaderNodeBump', Strength=0.1, Distance=0.0003)
    g.link(h, bump.inputs['Height']); g.link(bump.outputs['Normal'], bsdf.inputs['Normal'])
    bsdf.inputs['Roughness'].default_value = 0.7
    bsdf.inputs['Specular IOR Level'].default_value = 0.35
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
        # the planed flat face round the skin: same log, but its rings are cut so shallowly that
        # the bowl's slow warp turned them into broad ragged terraces; with little warp they read
        # as the long, straight stripes of a planed face (round 11)
        'woodTop': ring_wood('woodTop', *MULBERRY, (-8, -32), (0.22, 0.12), 1.6, 0.6, warp_cm=0.12, line_var=(0.55, 1.0)),
        # the lip under the skin's edge is bare wood: no satin coat (it caught the window as a pale band)
        'lip': ring_wood('lip', *(muted(c) for c in ('#76583f', '#664833', '#4a3326')), (-8, -32), (0.22, 0.12), 1.6, 0.7, line_var=(0.2, 0.6)),
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
    if os.environ.get('TAR_LOOK', 'samples') == 'samples':
        # round 13: the look of the user's sample sheets
        mats.update({
            'wood': rosewood('rw_bowl', stripes=16, stripe_axis_y=0.0895, stripe_top=0.34),
            'woodTop': rosewood('rw_top'),
            # the head's flat front faces the window squarely in the opening scenes and mirrored
            # it as a pale grey slab: a softer, satin finish keeps it dark red-brown
            'headWood': rosewood('rw_head', scale=2.0, gloss=0.0, spec=0.15, rough=0.6),
            'pegWood': rosewood('rw_peg', tones=('#1e0904', '#40150a', '#6a2a12', '#8a4020'), scale=3.0),
            'boardWood': rosewood('rw_board', tones=('#1a0703', '#33100a', '#561e0e', '#6e2a14'), scale=2.0),
            'lightWood': maple('maple'),
            'lip': khatam_lip(),
            'skin': parchment_skin(),
        })
    for o in bpy.context.scene.objects:
        if o.type != 'MESH':
            continue
        key = o.name.split('__')[-1].split('.')[0]
        if o.name.startswith('body__top') or o.name.startswith('heel__'):
            key = 'woodTop'  # the flat face and the heel: same wood, no inlay lines
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
    dark = nt.nodes.new('ShaderNodeBackground'); dark.inputs['Strength'].default_value = 1.0
    if os.environ.get('TAR_LOOK', 'samples') == 'samples':
        # round 13: the samples' charcoal studio — near-black above, a slightly lighter grey floor
        # where the camera looks down, with a faint texture so it is not a flat digital fill
        g = Nodes(nt)
        dirv = g.new('ShaderNodeSeparateXYZ'); g.link(tc.outputs['Generated'], dirv.inputs[0])
        floor = g.new('ShaderNodeMapRange', **{'From Min': 0.05, 'From Max': -0.35})
        floor.interpolation_type = 'SMOOTHSTEP'; g.link(dirv.outputs['Z'], floor.inputs['Value'])
        tex = g.noise(tc.outputs['Generated'], 180.0, detail=4, rough=0.6)
        base = g.mix(floor.outputs['Result'], srgb('#0f0f0f'), srgb('#232222'))
        base = g.mix(1.0, base, g.grey(g.op('ADD', 0.9, g.op('MULTIPLY', tex.outputs['Fac'], 0.2))), 'MULTIPLY')
        g.link(base, dark.inputs['Color'])
    else:
        dark.inputs['Color'].default_value = srgb('#0b0a09')
    lp = nt.nodes.new('ShaderNodeLightPath')
    mix = nt.nodes.new('ShaderNodeMixShader')
    nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
    lit = room.outputs['Background']
    if os.environ.get('TAR_LOOK', 'samples') == 'samples':
        # Round 13: in the high-gloss lacquer the HDRI's studio stands and fixtures showed as thin
        # bright outlines. Reflections see a clean studio instead: a soft, slightly warm ceiling
        # fading to a dark floor; the area lights give the broad softbox highlights.
        g = Nodes(nt)
        dz = g.new('ShaderNodeSeparateXYZ'); g.link(tc.outputs['Generated'], dz.inputs[0])
        dome = g.new('ShaderNodeMapRange', **{'From Min': -0.2, 'From Max': 0.9})
        dome.interpolation_type = 'SMOOTHSTEP'; g.link(dz.outputs['Z'], dome.inputs['Value'])
        clean = g.new('ShaderNodeBackground', Strength=1.0)
        g.link(g.mix(dome.outputs['Result'], (0.004, 0.004, 0.004, 1), (0.09, 0.08, 0.07, 1)), clean.inputs['Color'])
        gm = g.new('ShaderNodeMixShader')
        g.link(lp.outputs['Is Glossy Ray'], gm.inputs['Fac'])
        g.link(room.outputs['Background'], gm.inputs[1]); g.link(clean.outputs['Background'], gm.inputs[2])
        lit = gm.outputs['Shader']
    nt.links.new(lit, mix.inputs[1]); nt.links.new(dark.outputs['Background'], mix.inputs[2])
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
    window.data.specular_factor = 0.3
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
    rim = area('rim', (1.1, 1.6, 0.55), 0.8, 0.6, 45, (1.0, 0.9, 0.78))
    rim.data.specular_factor = 0.12  # round 13: the glossy lacquer mirrored it as a pale patch
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


# The scroll timeline (round 10): the seven scenes, then the tar falls over backwards about a
# hinge near its bottom end, and the rest of the scroll zooms in on its face.
TIMELINE = {
    'scenes_end': 0.60,   # the seven scenes play over 0…60 % of the scroll
    'front': 0.64,         # it turns to face the camera squarely (user, round 11)…
    'fall': (0.66, 0.82),  # …rests a moment, then falls straight over backwards…
    'zoom_end': 1.0,       # …and the camera comes down onto the face until the end
    # the hinge: on the back of the bowl, this many cm from the bottom end (TAR_HINGE_CM)
    'hinge_cm': float(os.environ.get('TAR_HINGE_CM', '10')),
    'fall_deg': 90,
    'crane_elev': 40,      # the camera rises while it falls, so it never sees it edge-on
    'face': [0, 15, 0.4],  # the point of the face the zoom ends on (web cm)
    'face_dist': 70, 'face_elev': 78,
}
BODY_BACK = None  # depth of the back of the bowl by height, read from the mesh in setup()


def hinge_local():
    y = TIMELINE['hinge_cm']
    return web_to_blender((0, y, BODY_BACK(y)))


def keyframe_state(p):
    """The seven web scenes, as before (p in 0…1 of their own span)."""
    kf = SCENES['keyframes']
    i = 0
    while i < len(kf) - 2 and p > kf[i + 1]['at']:
        i += 1
    a, b = kf[i], kf[i + 1]
    t = ease((p - a['at']) / (b['at'] - a['at']))
    qa, qb = pose_quaternion(a['yaw'], a['pitch']), pose_quaternion(b['yaw'], b['pitch'])
    lerp = lambda x, y: x + (y - x) * t
    q = qa.slerp(qb, t)
    world = Matrix.Translation(PIVOT) @ q.to_matrix().to_4x4() @ Matrix.Translation(-PIVOT)
    target = world @ web_to_blender([lerp(x, y) for x, y in zip(a['target'], b['target'])])
    e = math.radians(lerp(a['elev'], b['elev']))
    d = math.exp(lerp(math.log(a['dist']), math.log(b['dist']))) * CM
    return {
        'q': q, 'world': world, 'target': target,
        'cam': target + Vector((0, -math.cos(e) * d, math.sin(e) * d)),
        'exposure': lerp(a['exposure'], b['exposure']),
        'aperture': lerp(a.get('aperture', 0), b.get('aperture', 0)),
    }


def pose_state(k):
    """A single web-style pose as a scroll state."""
    q = pose_quaternion(k['yaw'], k['pitch'])
    world = Matrix.Translation(PIVOT) @ q.to_matrix().to_4x4() @ Matrix.Translation(-PIVOT)
    target = world @ web_to_blender(k['target'])
    e = math.radians(k['elev']); d = k['dist'] * CM
    return {'q': q, 'world': world, 'target': target,
            'cam': target + Vector((0, -math.cos(e) * d, math.sin(e) * d)),
            'exposure': 1.0, 'aperture': 0.0}


def blend_states(a, b, t):
    q = a['q'].slerp(b['q'], t)
    world = Matrix.Translation(PIVOT) @ q.to_matrix().to_4x4() @ Matrix.Translation(-PIVOT)
    return {'q': q, 'world': world, 'target': a['target'].lerp(b['target'], t), 'cam': a['cam'].lerp(b['cam'], t),
            'exposure': 1.0, 'aperture': 0.0}


def fall_angle(t):
    """Degrees fallen at t (0…1): gravity speeds it up, it lands a hair past flat and settles."""
    full = TIMELINE['fall_deg']
    if t < 0.82:
        return full * 1.02 * (t / 0.82) ** 2
    u = (t - 0.82) / 0.18
    return full * (1.02 - 0.02 * (1 - math.cos(math.pi * u)) / 2)


def sample_scroll(p):
    T = TIMELINE
    if p <= T['scenes_end']:
        return keyframe_state(p / T['scenes_end'])
    last = keyframe_state(1.0)
    # straight on: the fall is seen from the front, square, with no turn left or right
    front = dict(SCENES['keyframes'][-1], yaw=round(SCENES['keyframes'][-1]['yaw'] / 360) * 360, pitch=0, elev=2)
    end = pose_state(front)
    if p <= T['front']:
        return blend_states(last, end, ease((p - T['scenes_end']) / (T['front'] - T['scenes_end'])))
    q0, w0 = end['q'], end['world']
    h = w0 @ hinge_local()
    axis = q0 @ Vector((1, 0, 0))
    centre_local = PIVOT
    f0, f1 = T['fall']

    def fallen(deg):
        r = Quaternion(axis, -math.radians(deg)).to_matrix().to_4x4()
        return Matrix.Translation(h) @ r @ Matrix.Translation(-h) @ w0

    def orbit(target, dist_m, elev_deg):
        e = math.radians(elev_deg)
        return target + Vector((0, -math.cos(e) * dist_m, math.sin(e) * dist_m))

    start_dist = (end['cam'] - end['target']).length
    start_elev = math.degrees(math.asin(max(-1, min(1, (end['cam'] - end['target']).z / start_dist))))
    if p <= f0:  # a breath of stillness before it goes
        return end
    if p <= f1:
        t = (p - f0) / (f1 - f0)
        world = fallen(fall_angle(t))
        # the operator half follows the falling instrument and cranes up
        target = end['target'].lerp(world @ centre_local, 0.5 * ease(t))
        cam = orbit(target, start_dist, start_elev + (T['crane_elev'] - start_elev) * ease(t))
        return {'world': world, 'target': target, 'cam': cam, 'exposure': 1.0, 'aperture': 0.0}
    t = ease((p - f1) / (T['zoom_end'] - f1))
    world = fallen(T['fall_deg'])
    flat_target = end['target'].lerp(world @ centre_local, 0.5)
    target = flat_target.lerp(world @ web_to_blender(T['face']), t)
    dist = math.exp(math.log(start_dist) + (math.log(T['face_dist'] * CM) - math.log(start_dist)) * t)
    cam = orbit(target, dist, T['crane_elev'] + (T['face_elev'] - T['crane_elev']) * t)
    # the camera turns as it comes down so the instrument ends upright in the frame, head at the top
    head = (world.to_3x3() @ Vector((0, 0, 1))).normalized()
    up = Vector((0, 0, 1)).lerp(head, t).normalized()
    return {'world': world, 'target': target, 'cam': cam, 'exposure': 1.0, 'aperture': 0.0003 * t, 'up': up}


def apply_state(pivot, cam, s):
    # the pivot carries every part with a parent inverse of T(-PIVOT): child = pivot · T(-PIVOT)
    pivot.matrix_world = s['world'] @ Matrix.Translation(PIVOT)
    t = s['target']
    cam.location = s['cam']
    f = (t - cam.location).normalized()
    up_hint = s.get('up', Vector((0, 0, 1)))
    right = f.cross(up_hint).normalized()
    up = right.cross(f)
    cam.rotation_euler = Matrix((right, up, -f)).transposed().to_euler()
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
    pivot, objs = import_model()
    global BODY_BACK
    shell = [v.co for o in objs if o.name.startswith('body__shell') for v in o.data.vertices]
    def body_back(y_cm):
        near = [-c.y / CM for c in shell if abs(c.z / CM - y_cm) < 0.5]
        return min(near) if near else -20.0  # web z of the back (Blender y = -web z)
    BODY_BACK = body_back
    global SKIN_EDGE
    SKIN_EDGE = make_skin_edge_map(objs)
    global LIP_EDGE
    LIP_EDGE = mesh_edge_map(objs, 'body__lip', 'lip', max_cm=1.0)
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
    elif mode == 'at':
        # one scroll position at a chosen size: at <p> [width height samples]
        p = float(argv[1]); w, h, spp = (int(x) for x in (argv[2:5] if len(argv) >= 5 else (1600, 900, 96)))
        sc, pivot, cam = setup(w, h, spp)
        out = BUILD / 'at'; out.mkdir(parents=True, exist_ok=True)
        apply_state(pivot, cam, sample_scroll(p))
        render(sc, out / f'p{round(p * 1000):04d}_{w}.png', seed=round(p * 1000), raw_dir=out / 'raw')
    elif mode == 'tail':
        # quick look at the end of the scroll: the fall and the zoom (round 10)
        sc, pivot, cam = setup(960, 540, 32)
        out = BUILD / 'tail'; out.mkdir(parents=True, exist_ok=True)
        for p in (0.60, 0.64, 0.68, 0.72, 0.75, 0.78, 0.80, 0.82, 0.87, 0.93, 1.0):
            apply_state(pivot, cam, sample_scroll(p))
            render(sc, out / f'p{round(p * 100):03d}.png', seed=round(p * 1000), raw_dir=out / 'raw')
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
        # Round 16: the tar falls over backwards, so the sheet also covers it lying down and
        # turned further, showing the tail end, the underside and the back of the bowls from below.
        pitches = [int(p) for p in os.environ.get('TAR_SHEET_PITCHES', '-60,-30,0,30,60,-75,-90,-105,-120,-150,-180').split(',')]
        for pitch in pitches:
            for yaw in range(0, 360, 15):
                path = out / f'y{yaw:03d}_p{pitch:+03d}.png'
                if path.exists():
                    continue
                apply_pose(pivot, cam, yaw, pitch, [c['x'], c['y'], c['z']], 250, 0)
                render(sc, path, seed=10000 + yaw * 10 + pitch, raw_dir=HERE / 'frames_raw' / 'sheet_raw')


if __name__ == '__main__':
    main(sys.argv[1:])
