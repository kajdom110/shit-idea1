"""The fall shot (round 20): only the last movement of the tar. Seen from the front, it tips
straight over backwards onto a Persian carpet; when it lands on its back (−90°) a little dust
rises slowly from the carpet.

The fall is physical: the round back of the bowl rolls on the carpet without slipping (no
floating, no sinking in), slowly at first, gathering speed as gravity takes it, and the
landing ends in a small, damped rebound. The dust is a volume of fine particles — an
expanding, rising ring round the contact patch, broken up by noise and lit from behind — plus
a few hundred specks drifting up and out with air drag.

    python3 render/fall_cut.py test            # a few stills at 960×540
    python3 render/fall_cut.py frames [N]      # N (180) frames at 1600×900 → frames_raw/fall/
    python3 render/fall_cut.py at <t> [w h spp]
"""
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

import build_scene as B

HERE = Path(__file__).resolve().parent
OUT = HERE / 'frames_raw' / 'fall'

# timeline, as a fraction of the scroll
HOLD, IMPACT, REBOUND = 0.06, 0.5, 0.62

rng_seed = 11


# ---------------------------------------------------------------- the fall
def fall_angle(t):
    """Degrees fallen backwards at scroll position t."""
    if t <= HOLD:
        return 0.0
    if t <= IMPACT:
        u = (t - HOLD) / (IMPACT - HOLD)
        return 90.0 * u * u * (0.35 + 0.65 * u)   # starts very slowly, lands at full speed
    tau = (t - IMPACT) / (REBOUND - IMPACT)
    if tau >= 1:
        return 90.0
    return 90.0 - 2.2 * math.exp(-3.5 * tau) * abs(math.sin(math.pi * 2.0 * tau))   # damped rebound


class Roller:
    """Places the instrument for a fall angle so that the back of its bowl rolls on the floor."""

    def __init__(self, objs):
        shell = [o for o in objs if o.name.startswith('body__shell')][0]
        self.profile = [v.co.copy() for v in shell.data.vertices if abs(v.co.x) < 0.012]
        self.all = [v.co.copy() for o in objs for i, v in enumerate(o.data.vertices) if i % 7 == 0]
        self.floor = min(v.z for v in self.profile)
        self.table = []
        s, prev = 0.0, None
        for i in range(0, 961):   # every 0.1°
            th = i / 10
            R = Matrix.Rotation(-math.radians(th), 4, 'X')
            c = min(self.profile, key=lambda p: (R @ p).z)
            if prev is not None:
                s += (c - prev).length   # no slip: the floor contact moves by the arc rolled
            prev = c
            self.table.append((th, c, s))

    def world(self, th):
        th = max(0.0, min(96.0, th))
        i = min(len(self.table) - 1, int(round(th * 10)))
        _, c, s = self.table[i]
        R = Matrix.Rotation(-math.radians(th), 4, 'X')
        rc = R @ c
        # the contact point sits on the floor, moved back by the distance rolled
        T = Matrix.Translation(Vector((0.0, self.table[0][1].y + s - rc.y, self.floor - rc.z)))
        return T @ R

    def lowest_other(self, th):
        M = self.world(th)
        return min((M @ v).z for v in self.all) - self.floor


# ---------------------------------------------------------------- carpet
def add_carpet(centre):
    w, h = 2.0, 1.4
    bpy.ops.mesh.primitive_plane_add(size=1, location=(centre.x, centre.y, 0))
    c = bpy.context.object; c.name = 'carpet'
    c.scale = (h, w, 1)   # long side along y, where the instrument lies
    bpy.ops.object.transform_apply(scale=True)
    c.location.z = ROLL.floor - 0.0005
    m, nt, bsdf = B.new_mat('carpet'); g = B.Nodes(nt)
    uv = g.new('ShaderNodeTexCoord').outputs['UV']
    rot = g.new('ShaderNodeMapping'); rot.inputs['Rotation'].default_value = (0, 0, math.pi / 2)
    rot.inputs['Location'].default_value = (1, 0, 0)
    g.link(uv, rot.inputs['Vector'])
    img = B.image(nt, B.ASSETS / 'persian_carpet.png'); img.interpolation = 'Cubic'
    g.link(rot.outputs['Vector'], img.inputs['Vector'])
    # the pile: a scanned carpet normal map, tiled; fibres catch the light a little (sheen)
    tile = g.new('ShaderNodeMapping'); tile.inputs['Scale'].default_value = (5.0, 7.0, 1.0)
    g.link(uv, tile.inputs['Vector'])
    nimg = B.image(nt, B.ASSETS / 'dirty_carpet_nor_gl_2k.jpg', colour=False)
    g.link(tile.outputs['Vector'], nimg.inputs['Vector'])
    nm = g.new('ShaderNodeNormalMap', Strength=0.9); g.link(nimg.outputs['Color'], nm.inputs['Color'])
    g.link(nm.outputs['Normal'], bsdf.inputs['Normal'])
    pile = g.noise(g.new('ShaderNodeTexCoord').outputs['Object'], 900.0, detail=2)
    col = g.mix(1.0, img.outputs['Color'], g.grey(g.op('ADD', 0.86, g.op('MULTIPLY', pile.outputs['Fac'], 0.24))), 'MULTIPLY')
    # a pool of light: the carpet sinks into the dark away from the instrument, so its edges
    # never show as a rectangle floating in the black
    ob = g.new('ShaderNodeTexCoord').outputs['Object']
    sep = g.new('ShaderNodeSeparateXYZ'); g.link(ob, sep.inputs[0])
    rr = g.op('SQRT', g.op('ADD', g.op('POWER', g.op('DIVIDE', sep.outputs['X'], 0.8), 2.0), g.op('POWER', g.op('DIVIDE', sep.outputs['Y'], 1.05), 2.0)))
    pool = g.new('ShaderNodeMapRange', **{'From Min': 0.45, 'From Max': 0.95, 'To Min': 1.0, 'To Max': 0.0})
    pool.interpolation_type = 'SMOOTHSTEP'; g.link(rr, pool.inputs['Value'])
    col = g.mix(1.0, col, g.grey(g.op('MULTIPLY', pool.outputs['Result'], 0.8)), 'MULTIPLY')
    g.link(g.op('MULTIPLY', pool.outputs['Result'], 0.25), bsdf.inputs['Sheen Weight'])   # no grey sheen out in the dark
    g.link(g.op('MULTIPLY', pool.outputs['Result'], 0.2), bsdf.inputs['Specular IOR Level'])
    g.link(col, bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.92
    bsdf.inputs['Specular IOR Level'].default_value = 0.2
    bsdf.inputs['Sheen Weight'].default_value = 0.25
    bsdf.inputs['Sheen Roughness'].default_value = 0.4
    c.data.materials.append(m)
    return c


# ---------------------------------------------------------------- dust
DUST = {}


def add_dust(contact):
    """A volume of fine dust round the contact patch; its shape is driven per frame."""
    size = (0.95, 0.95, 0.4)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(contact.x, contact.y, ROLL.floor + size[2] / 2))
    d = bpy.context.object; d.name = 'dust'
    d.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)   # object coords in metres from the centre
    m = bpy.data.materials.new('dust'); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear(); g = B.Nodes(nt)
    out = g.new('ShaderNodeOutputMaterial')
    vol = g.new('ShaderNodeVolumePrincipled')
    vol.inputs['Color'].default_value = (0.66, 0.6, 0.52, 1)
    vol.inputs['Anisotropy'].default_value = 0.55   # fine dust scatters forward: it glows against back light
    g.link(vol.outputs['Volume'], out.inputs['Volume'])
    co = g.new('ShaderNodeTexCoord').outputs['Object']
    sep = g.new('ShaderNodeSeparateXYZ'); g.link(co, sep.inputs[0])
    vals = {k: g.new('ShaderNodeValue') for k in ('R', 'W', 'H', 'A', 'rise', 'swirl')}
    v = {k: n.outputs[0] for k, n in vals.items()}
    zr = g.op('ADD', sep.outputs['Z'], size[2] / 2)                     # height above the carpet
    # the contact patch is long along the bowl's back: squeeze y a little
    r = g.op('SQRT', g.op('ADD', g.op('POWER', sep.outputs['X'], 2.0), g.op('POWER', g.op('MULTIPLY', sep.outputs['Y'], 0.8), 2.0)))
    ring = g.op('EXPONENT', g.op('MULTIPLY', -1.0, g.op('POWER', g.op('DIVIDE', g.op('SUBTRACT', r, v['R']), v['W']), 2.0)))
    core = g.op('MULTIPLY', 0.45, g.op('EXPONENT', g.op('MULTIPLY', -1.0, g.op('POWER', g.op('DIVIDE', r, g.op('MULTIPLY', v['R'], 0.9)), 2.0))))
    vert = g.op('EXPONENT', g.op('MULTIPLY', -1.0, g.op('DIVIDE', zr, v['H'])))
    # billowing: noise that drifts upward and swirls as the dust rises
    mp = g.new('ShaderNodeMapping'); g.link(co, mp.inputs['Vector'])
    loc = g.new('ShaderNodeCombineXYZ'); g.link(g.op('MULTIPLY', v['rise'], -1.0), loc.inputs['Z'])
    g.link(loc.outputs[0], mp.inputs['Location'])
    rotz = g.new('ShaderNodeCombineXYZ'); g.link(v['swirl'], rotz.inputs['Z']); g.link(rotz.outputs[0], mp.inputs['Rotation'])
    n1 = g.noise(mp.outputs['Vector'], 9.0, detail=6, rough=0.6, distortion=0.6)
    n2 = g.noise(mp.outputs['Vector'], 34.0, detail=3, rough=0.5)
    br = g.new('ShaderNodeMapRange', **{'From Min': 0.42, 'From Max': 0.72, 'To Min': 0.0, 'To Max': 1.6})
    g.link(g.op('ADD', g.op('MULTIPLY', n1.outputs['Fac'], 0.8), g.op('MULTIPLY', n2.outputs['Fac'], 0.2)), br.inputs['Value'])
    dens = g.op('MULTIPLY', g.op('MULTIPLY', g.op('ADD', ring, core), vert), g.op('MULTIPLY', br.outputs['Result'], v['A']))
    g.link(dens, vol.inputs['Density'])
    d.data.materials.append(m)
    d.visible_shadow = False
    DUST['obj'], DUST['vals'] = d, vals
    # specks: a few hundred grains drifting up and out with air drag
    import random
    rnd = random.Random(rng_seed)
    sm = bpy.data.materials.new('speck'); sm.use_nodes = True
    sb = sm.node_tree.nodes['Principled BSDF']
    sb.inputs['Base Color'].default_value = (0.7, 0.62, 0.5, 1); sb.inputs['Roughness'].default_value = 0.9
    sb.inputs['Transmission Weight'].default_value = 0.3
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1.0)
    proto = bpy.context.object; proto.data.materials.append(sm); proto.hide_render = True; proto.name = 'speck_proto'
    specks = []
    for i in range(320):
        o = bpy.data.objects.new(f'speck{i}', proto.data); bpy.context.scene.collection.objects.link(o)
        a = rnd.uniform(0, 2 * math.pi); r0 = rnd.uniform(0.03, 0.14)
        sp = rnd.uniform(0.05, 0.5)
        o.scale = (rnd.uniform(0.0003, 0.0011),) * 3
        specks.append((o, contact.x + r0 * math.cos(a), contact.y + r0 * math.sin(a) / 0.8,
                       sp * math.cos(a), sp * math.sin(a), rnd.uniform(0.05, 0.45), rnd.uniform(0.0, 0.15)))
    DUST['specks'] = specks


def set_dust(t):
    d = DUST['obj']
    tau = (t - IMPACT) / (1 - IMPACT)
    on = tau > 0
    d.hide_render = not on
    for s in DUST['specks']:
        s[0].hide_render = not on
    if not on:
        return
    tau = min(1.0, tau)
    vals = DUST['vals']
    vals['R'].outputs[0].default_value = 0.05 + 0.32 * tau ** 0.6
    vals['W'].outputs[0].default_value = 0.035 + 0.12 * tau
    vals['H'].outputs[0].default_value = 0.012 + 0.15 * tau ** 0.8
    amp = min(1.0, tau / 0.05) * math.exp(-2.0 * max(0.0, tau - 0.05))
    vals['A'].outputs[0].default_value = 6.0 * amp   # a little dust, not a cloud (user)
    vals['rise'].outputs[0].default_value = 0.2 * tau
    vals['swirl'].outputs[0].default_value = 0.25 * tau
    secs = 2.5 * tau   # the whole drift is about 2.5 s of real time, played slowly
    k, ge = 2.2, 0.06   # air drag, and a little settling
    for o, x0, y0, vx, vy, vz, delay in DUST['specks']:
        tt = max(0.0, secs - delay)
        f = (1 - math.exp(-k * tt)) / k
        o.location = (x0 + vx * f, y0 + vy * f,
                      ROLL.floor + 0.002 + (vz + ge / k) * f - ge * tt / k)
        o.hide_render = tt <= 0


# ---------------------------------------------------------------- camera
def camera_state(t, contact):
    """From the front, a little above; it follows the instrument down and moves in for the dust."""
    stand = Vector((0.0, 0.0, ROLL.floor + 0.47))
    lie = Vector((contact.x, contact.y + 0.22, ROLL.floor + 0.06))
    e = B.ease(min(1.0, max(0.0, (t - HOLD) / (REBOUND - HOLD))))
    target = stand.lerp(lie, e)
    dist = 3.3 + (1.9 - 3.3) * e
    elev = 6.0 + (46.0 - 6.0) * e   # looks down at the lying instrument and the dust round it
    if t > REBOUND:   # slow push-in while the dust drifts
        u = (t - REBOUND) / (1 - REBOUND)
        dist -= 0.3 * u
        target = target + Vector((0, 0, 0.03 * u))
    el = math.radians(elev)
    return target, target + Vector((0, -math.cos(el) * dist, math.sin(el) * dist))


# ---------------------------------------------------------------- setup and render
ROLL = None


def setup(w, h, spp):
    global ROLL
    sc, pivot, cam = B.setup(w, h, spp)
    objs = [o for o in bpy.data.objects if o.type == 'MESH' and '__' in o.name]
    ROLL = Roller(objs)
    end = ROLL.world(90.0)
    shell = [o for o in objs if o.name.startswith('body__shell')][0]
    contact_local = min(ROLL.profile, key=lambda p: (end @ p).z)
    contact = end @ contact_local
    add_carpet(Vector((0.0, contact.y + 0.25, 0)))
    add_dust(contact)
    sc.cycles.volume_step_rate = float(os.environ.get('FALL_VOL_STEP', '4.0'))
    sc.cycles.volume_max_steps = 256
    print('floor', round(ROLL.floor, 4), 'contact', tuple(round(c, 3) for c in contact),
          'clearance of other parts at 90°', round(ROLL.lowest_other(90.0), 4))
    return sc, pivot, cam, contact


def apply(t, pivot, cam, contact):
    pivot.matrix_world = ROLL.world(fall_angle(t)) @ Matrix.Translation(B.PIVOT)
    target, loc = camera_state(t, contact)
    cam.location = loc
    cam.rotation_euler = (target - loc).to_track_quat('-Z', 'Y').to_euler()
    cam.data.dof.use_dof = True
    cam.data.dof.focus_distance = (target - loc).length
    cam.data.dof.aperture_fstop = 8.0
    bpy.context.scene.view_settings.exposure = 0.0
    set_dust(t)


def main(argv):
    mode = argv[0] if argv else 'test'
    if mode == 'test':
        sc, pivot, cam, contact = setup(960, 540, 48)
        out = B.BUILD / 'fall_test'; out.mkdir(parents=True, exist_ok=True)
        for t in [float(x) for x in os.environ.get('FALL_TEST_T', '0,0.25,0.42,0.5,0.56,0.7,0.85,1').split(',')]:
            apply(t, pivot, cam, contact)
            B.render(sc, out / f't{round(t * 100):03d}.png', seed=round(t * 100), raw_dir=out / 'raw')
    elif mode == 'at':
        t = float(argv[1]); w, h, spp = (int(x) for x in (argv[2:5] if len(argv) >= 5 else (1600, 900, 96)))
        sc, pivot, cam, contact = setup(w, h, spp)
        out = B.BUILD / 'fall_at'; out.mkdir(parents=True, exist_ok=True)
        apply(t, pivot, cam, contact)
        B.render(sc, out / f't{round(t * 1000):04d}_{w}.png', seed=round(t * 1000), raw_dir=out / 'raw')
    elif mode == 'frames':
        n = int(argv[1]) if len(argv) > 1 else 180
        sc, pivot, cam, contact = setup(1600, 900, 48)
        OUT.mkdir(parents=True, exist_ok=True)
        for f in range(n):
            path = OUT / f'{f:04d}.png'
            if path.exists():
                continue
            apply(f / (n - 1), pivot, cam, contact)
            B.render(sc, path, seed=20000 + f, raw_dir=HERE / 'frames_raw' / 'fall_raw')


if __name__ == '__main__':
    main(sys.argv[1:])
