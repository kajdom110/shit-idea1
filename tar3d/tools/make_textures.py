"""Generate the tileable textures in tar3d/textures/ (phase 5).

Wood is not here: it is computed in the shader in 3D so its grain is continuous on every
surface (see tar3d/materials/woodShader.js). This script makes the textures that are
genuinely 2D: lamb skin, bone, the khatam inlay band and the gut of the frets.

    python3 tar3d/tools/make_textures.py

Needs NumPy and Pillow. Output is deterministic (fixed seeds).
"""
from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parent.parent / 'textures'


def value_noise(size, cells, rng, sx=1.0, sy=1.0):
    """Tileable value noise: random grid of `cells` (stretched by sx, sy), smoothly interpolated."""
    cx, cy = max(1, int(cells * sx)), max(1, int(cells * sy))
    grid = rng.random((cy, cx))
    ys = np.linspace(0, cy, size, endpoint=False)
    xs = np.linspace(0, cx, size, endpoint=False)
    y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
    fy, fx = ys - y0, xs - x0
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    y1, x1 = (y0 + 1) % cy, (x0 + 1) % cx
    a = grid[y0][:, x0]; b = grid[y0][:, x1]
    c = grid[y1][:, x0]; d = grid[y1][:, x1]
    top = a + (b - a) * fx[None, :]
    bot = c + (d - c) * fx[None, :]
    return top + (bot - top) * fy[:, None]


def fbm(size, base_cells, octaves, rng, sx=1.0, sy=1.0, gain=0.5):
    out = np.zeros((size, size)); amp = 1.0; total = 0.0; cells = base_cells
    for _ in range(octaves):
        out += amp * value_noise(size, cells, rng, sx, sy)
        total += amp; amp *= gain; cells *= 2
    return out / total


def save_rgb(arr, name, quality=88):
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), 'RGB').save(OUT / name, 'WEBP', quality=quality, method=6)


def save_grey(arr, name, quality=90):
    Image.fromarray(np.clip(arr * 255, 0, 255).astype(np.uint8), 'L').save(OUT / name, 'WEBP', quality=quality, method=6)


def mix(a, b, t):
    t = t[..., None]
    return np.array(a, float) * (1 - t) + np.array(b, float) * t


def skin(size=2048):
    """Lamb skin: grey-brown, cloudy where thinner, irregular dark stains, fine fibres, specks."""
    rng = np.random.default_rng(11)
    cloud = fbm(size, 3, 6, rng)
    stains = fbm(size, 4, 5, rng)
    stain_mask = np.clip((stains - 0.58) / 0.12, 0, 1) ** 1.5
    fibre_dir = fbm(size, 2, 3, rng)
    fibres = fbm(size, 48, 3, rng, sx=1.0, sy=0.35) * 0.6 + fbm(size, 90, 2, rng) * 0.4
    specks = (rng.random((size, size)) < 0.0015).astype(float)
    specks = np.maximum(specks, np.roll(specks, 1, 0) * 0.6)

    t = np.clip(cloud * 1.15 - 0.1 + (fibres - 0.5) * 0.25 + (fibre_dir - 0.5) * 0.1, 0, 1)
    col = mix((92, 82, 70), (162, 150, 130), t)
    col = col * (1 - 0.55 * stain_mask[..., None]) + np.array([38, 30, 22]) * 0.55 * stain_mask[..., None]
    col = col * (1 - 0.6 * specks[..., None])
    save_rgb(col, 'skin_albedo.webp')

    height = np.clip(0.5 + (fibres - 0.5) * 0.9 + (cloud - 0.5) * 0.3 - specks * 0.3, 0, 1)
    save_grey(height, 'skin_height.webp')


def bone(size=1024):
    """Bone / ivory: warm cream with faint streaks running along the length (v), and pores."""
    rng = np.random.default_rng(23)
    streak = fbm(size, 24, 4, rng, sx=1.0, sy=0.08)
    broad = fbm(size, 3, 4, rng)
    pores = (rng.random((size, size)) < 0.0008).astype(float)
    t = np.clip(streak * 0.7 + broad * 0.4 - 0.1, 0, 1)
    col = mix((206, 190, 158), (238, 228, 204), t)
    col = col * (1 - 0.35 * pores[..., None])
    save_rgb(col, 'bone_albedo.webp')
    save_grey(np.clip(0.5 + (streak - 0.5) * 0.6 - pores * 0.4, 0, 1), 'bone_height.webp')


def khatam(size=512, tiles=8):
    """Khatam inlay: rows of small triangles in bone, dark wood and brass."""
    rng = np.random.default_rng(5)
    yy, xx = np.mgrid[0:size, 0:size] / (size / tiles)
    fx, fy = xx % 1, yy % 1
    row = np.floor(yy).astype(int)
    up = (np.abs(fx - 0.5) * 2 <= fy)  # upward triangle in each cell
    flip = (row % 2 == 1)
    up = np.where(flip, ~up, up)
    bone_c = np.array([226, 212, 178.]); wood_c = np.array([62, 36, 18.]); brass_c = np.array([186, 146, 78.])
    col = np.where(up[..., None], bone_c, wood_c)
    brass_line = (np.abs(fy - 0.5) < 0.05)
    col = np.where(brass_line[..., None], brass_c, col)
    grain = fbm(size, 32, 3, rng)
    col = col * (0.9 + 0.2 * grain[..., None])
    save_rgb(col, 'khatam.webp')
    save_grey(np.where(brass_line, 0.65, np.where(up, 0.55, 0.45)), 'khatam_height.webp')


def gut(w=256, h=64):
    """Gut fret strand: pale straw, a slow twist of darker and lighter fibres (u = along)."""
    rng = np.random.default_rng(3)
    yy, xx = np.mgrid[0:h, 0:w]
    twist = np.sin((xx / w * 6 + yy / h) * 2 * np.pi) * 0.5 + 0.5
    n = value_noise(256, 32, rng)[:h, :w]
    t = np.clip(twist * 0.6 + n * 0.4, 0, 1)
    col = mix((196, 168, 108), (238, 222, 172), t)
    Image.fromarray(np.clip(col, 0, 255).astype(np.uint8), 'RGB').save(OUT / 'gut.webp', 'WEBP', quality=90)


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    skin(); bone(); khatam(); gut()
    for p in sorted(OUT.glob('*.webp')):
        print(f'{p.name:22s} {p.stat().st_size // 1024:5d} KB')
