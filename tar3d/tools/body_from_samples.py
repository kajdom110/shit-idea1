"""Body profiles from the user's sample sheets (round 14, docs/tar-3d/refs-chatgpt).

The half-width of the outline is measured on the two back views (A_fall_000_back, B_fall_000),
averaged and scaled to the body length; the waist, darkened by shadow in the samples, is held
at the width it shows by eye. The face is filled almost edge to edge by the skin, as on the
samples' top views: the skin and the khatam border are inward offsets of the outline (done on
a raster, so their ends round off properly). The depth follows the width: two egg-shaped bowls.

    python3 tar3d/tools/body_from_samples.py   # writes tar3d/bodyData.js
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[2]
REFS = ROOT / 'docs/tar-3d/refs-chatgpt'
LENGTH = 38.0          # body length, cm (unchanged: the neck and everything above stay put)
WAIST_HALF = 5.0       # cm; the samples' waist by eye (the mask pinches it in shadow)
LIP_IN = 0.9           # cm from the outline to the outer edge of the khatam border
SKIN_IN = 1.9          # cm from the outline to the skin's edge
DEPTH_PER_HALF = 1.75  # bowl depth / half-width
DEPTH_MIN = 11.0


def back_profile(name):
    im = np.asarray(Image.open(REFS / f'{name}.webp').convert('RGB')).astype(float)
    obj = ((im[..., 0] - im[..., 2]) > 18) | (im.mean(2) > 70)
    w = np.array([(np.ptp(np.where(r)[0]) if r.sum() > 3 else 0) for r in obj])
    bottom = max(y for y in range(len(w)) if w[y] > 25)
    y = bottom
    while w[y] < 60: y -= 1
    while w[y] >= 30: y -= 1
    L = bottom - y
    t = np.linspace(0, 1, 200)
    return t, np.array([w[int(round(bottom - s * L))] / 2 / L for s in t])


t, a = back_profile('A_fall_000_back')
_, b = back_profile('B_fall_000')
measured = (a + b) / 2 * LENGTH
ys = t * LENGTH
# The samples' bowls are two eggs seen from the front: the measured widths (lower bowl 11.25,
# upper 9.0 half-width) and positions, drawn as two ovals joined by a smooth waist, so the sides
# are round all the way (the raw measurement has flat sides where shadow eats the silhouette).
LOWER = dict(cy=12.0, rx=float(measured[(ys > 4) & (ys < 14)].max()), ry=12.0)
UPPER = dict(cy=28.9, rx=float(measured[(ys > 26) & (ys < 34)].max()), ry=9.5)


def oval(e, y):
    u = (y - e['cy']) / e['ry']
    return e['rx'] * np.sqrt(np.clip(1 - u * u, 0, None))


lo, up = oval(LOWER, ys), oval(UPPER, ys)
smooth = 1.2  # cm: rounds the join at the waist (a smooth maximum)
half = smooth * np.log(np.exp(lo / smooth) + np.exp(up / smooth)) - smooth * np.log(2) * np.exp(-np.abs(lo - up) / smooth)
half = np.maximum(half, np.maximum(lo, up))
print('lower', LOWER, 'upper', UPPER)
# the neck leaves the top of the upper bowl: never narrower than the neck there
half = np.where(ys > 36, np.maximum(half, 2.3), half)

# inward offsets on a raster of the face (0.05 cm per pixel)
PX = 20
Wpx, Hpx = int(2 * (half.max() + 1) * PX), int((LENGTH + 2) * PX)
cx = Wpx / 2
poly = [(cx + h * PX, Hpx - (y + 1) * PX) for y, h in zip(ys, half)] + \
       [(cx - h * PX, Hpx - (y + 1) * PX) for y, h in reversed(list(zip(ys, half)))]
face = Image.new('L', (Wpx, Hpx), 0); ImageDraw.Draw(face).polygon(poly, fill=255)


def offset(img, cm):
    for _ in range(round(cm * PX)):
        img = img.filter(ImageFilter.MinFilter(3))
    return np.asarray(img) > 127


def half_widths(mask, step=0.05):
    out = []
    for y in np.arange(0, LENGTH + 1e-6, step):
        row = mask[int(round(Hpx - (y + 1) * PX))]
        xs = np.where(row)[0]
        out.append((round(y, 3), round(max(0.0, (xs.max() - cx) / PX), 3) if len(xs) else 0.0))
    # keep only the run where it exists, with a zero at each end (as the old data)
    nz = [i for i, (_, v) in enumerate(out) if v > 0]
    return out[max(0, nz[0] - 1): nz[-1] + 2]


# Round 15: the skin does NOT cover the whole face. As on a real tar (the user's photo,
# docs/tar-3d SPEC section 25) it covers two separate shapes whose points almost meet at the
# waist: a teardrop on the kaseh (round bottom, point up) and a heart on the naghareh (round
# top, point down), each a little over half the width of its bowl, with the round wood of the
# bowl all round them. Sizes are fractions of the bowls, so they follow the outline above.
SKIN_LOWER = dict(bottom=6.5, widest=13.0, point=22.3, frac=0.62)
SKIN_UPPER = dict(point=23.3, widest=31.3, top=36.6, frac=0.56)
BORDER = 0.9  # cm: the khatam border round each skin


def teardrop(y):
    e = SKIN_LOWER; R = e['frac'] * LOWER['rx']
    if e['bottom'] <= y <= e['widest']:
        u = (e['widest'] - y) / (e['widest'] - e['bottom'])
        return R * np.sqrt(max(0.0, 1 - u * u))
    if e['widest'] < y <= e['point']:
        u = (y - e['widest']) / (e['point'] - e['widest'])
        return R * np.cos(u * np.pi / 2) ** 1.25  # full shoulders, then a fine point
    return 0.0


def heart(y):
    e = SKIN_UPPER; R = e['frac'] * UPPER['rx']
    if e['widest'] <= y <= e['top']:
        u = (y - e['widest']) / (e['top'] - e['widest'])
        return R * np.sqrt(max(0.0, 1 - u * u))
    if e['point'] <= y < e['widest']:
        u = (e['widest'] - y) / (e['widest'] - e['point'])
        return R * np.cos(u * np.pi / 2) ** 1.25
    return 0.0


grid = np.round(np.arange(0, LENGTH + 1e-6, 0.05), 3)
skin_half = np.array([max(teardrop(y), heart(y)) for y in grid])
# the border: the two skin shapes grown outward by BORDER cm (on a raster, so it rounds the points)
m = np.zeros((Hpx, Wpx), np.uint8)
xs_px = (np.arange(Wpx) - cx) / PX
for row in range(Hpx):
    y = (Hpx - row) / PX - 1
    h = max(teardrop(y), heart(y))
    if h > 0:
        m[row, np.abs(xs_px) <= h] = 255
sk = Image.fromarray(m)
grown = sk
for _ in range(round(BORDER * PX)):
    grown = grown.filter(ImageFilter.MaxFilter(3))
lip = half_widths(np.asarray(grown) > 127)
nz = np.where(skin_half > 0)[0]
skin = [(float(grid[i]), round(float(skin_half[i]), 3)) for i in range(max(0, nz[0] - 1), min(len(grid), nz[-1] + 2))]
outline = [(round(y, 3), round(h, 3)) for y, h in zip(ys, half)]
depth = [(round(y, 3), round(max(DEPTH_MIN, DEPTH_PER_HALF * h), 3)) for y, h in zip(ys, half)]
# the bottom and the shoulders round off: depth follows the outline down to a few cm there
depth = [(y, round(min(d, DEPTH_PER_HALF * h + 1.0), 3)) for (y, d), (_, h) in zip(depth, outline)]


def js(name, comment, pts):
    body = ',\n'.join(f'  [{y}, {v}]' for y, v in pts)
    return f'// {comment}\nexport const {name} = [\n{body},\n];\n'


out = ['// Generated by tools/body_from_samples.py — do not edit by hand.',
       '// Profiles of the body in centimetres: [y from the bottom of the kaseh, value].',
       '// Round 14: shaped after the user\'s sample sheets (docs/tar-3d/refs-chatgpt).', '',
       js('OUTLINE', 'Half-width of the outline seen from the front (samples, back views).', outline),
       js('DEPTH', 'Depth of the bowl below the face: follows the width, two egg-shaped bowls.', depth),
       js('SKIN', 'Half-width of the skin: a teardrop on the kaseh and a heart on the naghareh.', skin),
       js('LIP', 'Half-width of the outer edge of the khatam border round the two skins.', lip)]
(ROOT / 'tar3d/bodyData.js').write_text('\n'.join(out))
for y in (2, 5, 8.5, 13, 17, 20, 22, 25, 30, 34, 37):
    i = int(round(y / LENGTH * 199))
    print(f'y {y:5}: half {half[i]:.2f}  depth {depth[i][1]:.2f}')
print('skin', skin[0][0], '…', skin[-1][0], ' lip', lip[0][0], '…', lip[-1][0])
