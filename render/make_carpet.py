"""A hand-knotted Persian carpet design, drawn as an image for the fall shot (round 20).

No free scan of a Persian rug exists, so the design is drawn here: a deep red field with a
lattice of small rosettes and vines, a lobed central medallion, quarter-medallion corners, a
dark blue main border of rosettes and palmettes between thin guard stripes. It is then given
the look of real knotting: colour quantised to a knot grid, abrash (bands of slightly
different dye lots), small irregularities and wear. The pile itself (fibres and relief) comes
from a scanned carpet normal map in the material.

    python3 render/make_carpet.py   # writes render/assets/persian_carpet.png (2 mm per pixel)
"""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
W_CM, H_CM = 200.0, 140.0   # carpet size
PX = 8                      # pixels per cm
W, H = int(W_CM * PX), int(H_CM * PX)
rng = np.random.default_rng(7)

PAL = {
    'red': (122, 22, 24), 'red_dark': (84, 14, 18), 'navy': (24, 32, 62), 'ivory': (214, 196, 160),
    'gold': (186, 140, 64), 'green': (52, 82, 64), 'sky': (92, 122, 150), 'brown': (58, 34, 22),
    'pink': (170, 92, 88),
}
img = np.zeros((H, W, 3), np.float32)
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
X, Y = (xx - W / 2) / PX, (yy - H / 2) / PX   # cm from the centre


def paint(mask, colour, alpha=1.0):
    m = np.clip(mask, 0, 1)[..., None] * alpha
    img[:] = img * (1 - m) + np.array(PAL[colour], np.float32) * m


def soft(d, w=0.25):
    """1 inside (d < 0), 0 outside, with a soft edge w cm wide."""
    return np.clip(0.5 - d / w, 0, 1)


# ---- field: red with a herati pattern — a rosette in a diamond, four lancet leaves curling
# round it, small blossoms at the diamond's corners — and a second, offset grid of florets
img[:] = PAL['red']
cell = 8.0
cx, cy = np.round(X / cell) * cell, np.round(Y / cell) * cell
lx, ly = X - cx, Y - cy
r = np.hypot(lx, ly); th = np.arctan2(ly, lx)
diamond = np.abs(lx) + np.abs(ly)
paint(soft(np.abs(diamond - 3.6) - 0.12, 0.12), 'navy')                       # diamond outline
for k in range(4):                                                            # lancet leaves
    a_ = k * np.pi / 2 + np.pi / 4 + 0.35
    u = lx * np.cos(a_) + ly * np.sin(a_); v = -lx * np.sin(a_) + ly * np.cos(a_)
    leaf = soft(np.hypot((u - 3.0) / 1.5, (v - 0.25 * (u - 3.0) ** 2) / 0.45) - 1, 0.12)
    paint(leaf, 'green' if k % 2 else 'sky', 0.95)
    paint(soft(np.hypot((u - 3.0) / 1.5, v / 0.12) - 1, 0.1) * leaf, 'ivory', 0.6)
paint(soft(r - (1.5 + 0.35 * np.cos(8 * th))), 'ivory')
paint(soft(r - (1.0 + 0.2 * np.cos(8 * th + 0.4))), 'pink')
paint(soft(r - 0.55), 'gold'); paint(soft(r - 0.25), 'navy')
for tx, ty in ((3.6, 0), (-3.6, 0), (0, 3.6), (0, -3.6)):                      # corner blossoms
    rb = np.hypot(lx - tx, ly - ty); tb = np.arctan2(ly - ty, lx - tx)
    paint(soft(rb - (0.6 + 0.2 * np.cos(6 * tb)), 0.1), 'gold'); paint(soft(rb - 0.22, 0.1), 'red_dark')
bx, by = X - (np.floor(X / cell) + 0.5) * cell, Y - (np.floor(Y / cell) + 0.5) * cell
br = np.hypot(bx, by); bth = np.arctan2(by, bx)
paint(soft(br - (0.7 + 0.25 * np.cos(5 * bth))), 'ivory', 0.9); paint(soft(br - 0.28), 'green')

# ---- central medallion and corner quarter-medallions
def medallion(cx_, cy_, rx, ry):
    dx, dy = (X - cx_) / rx, (Y - cy_) / ry
    rr = np.hypot(dx, dy); t = np.arctan2(dy, dx)
    lobes = 1 + 0.06 * np.cos(16 * t) + 0.035 * np.cos(32 * t) + 0.02 * np.cos(48 * t)
    edge = (rr - lobes) * rx
    paint(soft(edge + 1.4, 0.25), 'ivory')
    paint(soft(edge + 2.2, 0.25), 'navy')
    # the navy ground is filled with gold tendrils and small ivory flowers
    tend = soft(np.abs(np.sin(10 * t + 6 * rr)) - 0.12, 0.08) * soft(edge + 3.2, 0.3) * (rr > 0.66)
    paint(tend, 'gold', 0.85)
    fl = np.hypot(((t * 16 / (2 * np.pi)) % 1 - 0.5) * 2 * np.pi * rr * rx / 16, (rr - 0.82) * rx) - 0.9
    paint(soft(fl, 0.15) * (rr < 0.95), 'ivory')
    ring = rr - (0.62 + 0.04 * np.cos(12 * t))
    paint(soft(ring * rx + 0.5, 0.25), 'ivory')
    paint(soft(ring * rx, 0.25), 'red')
    arab = soft(np.abs(np.sin(6 * t) * rr * rx * 0.9 - 2.2 * np.cos(rr * 9)) - 0.35, 0.2) * soft(ring * rx + 0.5, 0.25)
    paint(arab, 'gold')
    star = rr * rx - (5.5 + 1.6 * np.abs(np.cos(4 * t)) ** 3)
    paint(soft(star + 0.5, 0.2), 'ivory'); paint(soft(star, 0.2), 'navy')
    paint(soft(rr * rx - (2.6 + 0.5 * np.cos(8 * t)), 0.2), 'sky')
    paint(soft(rr * rx - 1.6, 0.2), 'ivory'); paint(soft(rr * rx - 0.9, 0.2), 'red')
    for s_ in (1, -1):   # pendants
        pd = np.hypot((X - cx_ - s_ * (rx + 6)) / 3.5, (Y - cy_) / 4.5) - 1
        paint(soft(pd * 3.5 + 0.5, 0.25), 'ivory'); paint(soft(pd * 3.5, 0.25), 'navy'); paint(soft((pd + 0.5) * 3.5, 0.25), 'gold')


medallion(0, 0, 30, 22)
fx, fy = W_CM / 2 - 22, H_CM / 2 - 22   # inner edge of the borders
for sx in (1, -1):
    for sy in (1, -1):
        d = np.hypot((X - sx * fx) / 26, (Y - sy * fy) / 20)
        t = np.arctan2(Y - sy * fy, X - sx * fx)
        edge = d - (1 + 0.06 * np.cos(14 * t))
        paint(soft(edge * 22 + 1.0, 0.3), 'ivory'); paint(soft(edge * 22 + 2.2, 0.3), 'navy')
        inside = soft(edge * 22 + 2.2, 0.3)
        paint(inside * soft(np.abs(np.sin(9 * t + 5 * d)) - 0.12, 0.08), 'gold', 0.85)
        cr = np.hypot(((X + 100) % 5) - 2.5, ((Y + 100) % 5) - 2.5)
        paint(inside * soft(cr - 0.7, 0.15) * (d < 0.85), 'ivory')

# ---- borders: guard stripes, a navy main border with rosettes and palmettes
dist = np.minimum(W_CM / 2 - np.abs(X), H_CM / 2 - np.abs(Y))    # cm from the outer edge
along = np.where(W_CM / 2 - np.abs(X) < H_CM / 2 - np.abs(Y), Y, X)
band = lambda a, b: (dist >= a) & (dist < b)
paint(band(0, 1.2), 'brown')
paint(band(1.2, 2.4), 'ivory'); paint(band(1.2, 2.4) & (np.abs(((along * 1.5) % 2) - 1) < (dist - 1.2) / 1.2), 'red')
paint(band(2.4, 3.0), 'navy')
paint(band(3.0, 17.0), 'navy')
bp = ((along + 1000) % 12.0) - 6.0; bq = dist - 10.0
rr = np.hypot(bp, bq); tt = np.arctan2(bq, bp)
paint(band(3.0, 17.0) * soft(rr - (3.2 + 0.6 * np.cos(8 * tt))), 'red')
paint(band(3.0, 17.0) * soft(rr - (2.2 + 0.3 * np.cos(8 * tt))), 'ivory')
paint(band(3.0, 17.0) * soft(rr - 1.0), 'gold')
pp = ((along + 1006) % 12.0) - 6.0
palm = np.hypot(pp / 1.6, (bq + 1.5 * np.sin(pp * 0.8)) / 3.6) - 1
paint(band(3.0, 17.0) * soft(palm * 2, 0.3), 'green'); paint(band(3.0, 17.0) * soft((palm + 0.45) * 2, 0.3), 'pink')
vinep = soft(np.abs(bq - 4.5 * np.sin(along * 2 * np.pi / 12)) - 0.25, 0.2) * band(4.0, 16.0) * (rr > 3.6) * (palm > 0.1)
paint(vinep, 'gold')
paint(band(17.0, 17.6), 'ivory')
paint(band(17.6, 19.4), 'red'); paint(band(17.6, 19.4) * (np.abs(((along * 1.2) % 2) - 1) < 0.4), 'gold')
paint(band(19.4, 20.0), 'ivory'); paint(band(20.0, 21.0), 'navy')

# ---- knotting: quantise to a knot grid (about 3 knots per cm), abrash, wear
k = 3.2 / PX   # knots per pixel
small = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).resize((int(W * k), int(H * k)), Image.BOX)
a = np.asarray(small).astype(np.float32)
hk, wk = a.shape[:2]
a *= 1 + 0.06 * rng.standard_normal((hk, wk, 1)).astype(np.float32)            # knot to knot
rows = np.cumsum(rng.standard_normal(hk)) * 0.01
a *= (1 + (rows - rows.mean()))[:, None, None] * np.array([1.0, 0.98, 0.97])   # abrash bands
img = np.asarray(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).resize((W, H), Image.NEAREST)).astype(np.float32)
img = np.asarray(Image.fromarray(img.astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.6))).astype(np.float32)
wear = np.asarray(Image.fromarray((rng.random((H // 40, W // 40)) * 255).astype(np.uint8)).resize((W, H), Image.BICUBIC)).astype(np.float32) / 255
img *= (0.88 + 0.16 * wear)[..., None]
img = img * 0.92 + img.mean(2, keepdims=True) * 0.08   # old, slightly faded dyes
out = HERE / 'assets' / 'persian_carpet.png'
Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(out)
print('wrote', out, W, H)
