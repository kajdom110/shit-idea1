"""The small flaws of a real photograph, applied to each rendered frame.

A path tracer gives a perfect image: even exposure, no lens, no sensor. Real photos of an
instrument never look like that, and the eye notices. This adds, gently:

- a lens that is a little darker at the corners, and not exactly round or centred;
- exposure that is not perfectly even across the frame (a light that falls off);
- a soft halo round the brightest highlights (bloom of a real lens);
- a trace of colour fringing towards the edges (lateral chromatic aberration);
- sensor grain, stronger in the shadows, different in every frame;
- a soft shoulder in the highlights, as film and good sensors have, so nothing burns to white.

Every effect is seeded and depends only on the frame's position, so a frame re-rendered
later is identical, and neighbouring frames differ only in their grain.

    python3 photo_finish.py in.png out.png [seed]
"""
import sys

import numpy as np
from PIL import Image, ImageFilter


def _scale_channel(ch, factor):
    """Scales one channel about the image centre (for colour fringing)."""
    h, w = ch.shape
    im = Image.fromarray(ch, mode='F')
    nw, nh = round(w * factor), round(h * factor)
    im = im.resize((nw, nh), Image.BICUBIC)
    x0, y0 = (nw - w) // 2, (nh - h) // 2
    return np.asarray(im.crop((x0, y0, x0 + w, y0 + h)), dtype=np.float32)


def finish(img, seed=0, grain=1.0):
    a = np.asarray(img.convert('RGB'), dtype=np.float32) / 255.0
    h, w, _ = a.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    # normalised coordinates, -1…1 on the short side
    s = min(w, h) / 2
    x, y = (xx - w / 2) / s, (yy - h / 2) / s

    # 0. a film-like shoulder: tones above 0.78 roll off gently instead of clipping, so
    # a brightly lit face keeps its grain and texture (round 9)
    k = 0.78
    over = np.maximum(a - k, 0)
    a = np.minimum(a, k) + (1 - k) * (1 - np.exp(-over / (1 - k)))

    # 1. bloom: a soft halo round the highlights
    lum = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    hi = np.clip((lum - 0.62) / 0.38, 0, 1)[..., None] * a
    hi_img = Image.fromarray((hi * 255).astype(np.uint8))
    halo = np.asarray(hi_img.filter(ImageFilter.GaussianBlur(radius=max(w, h) / 90)), dtype=np.float32) / 255.0
    a = a + halo * 0.18

    # 2. lateral chromatic aberration: red a touch larger, blue a touch smaller
    a[..., 0] = _scale_channel(a[..., 0], 1.0007)
    a[..., 2] = _scale_channel(a[..., 2], 0.9993)

    # 3. vignette: slightly oval and a little off centre, as on a real lens and sensor
    r2 = ((x - 0.04) / 1.25) ** 2 + ((y + 0.03) / 1.1) ** 2
    a *= (1 - 0.28 * np.clip(r2, 0, 2.5) / 2.5)[..., None] ** 1.0

    # 4. light falling off across the frame: the window is up and to the left
    fall = 1 + 0.05 * (-x * 0.6 - y * 0.8) / 2
    a *= fall[..., None]

    # 5. grain: fine, slightly coloured, stronger in the shadows; new in every frame
    rng = np.random.default_rng(seed)
    n = rng.normal(0, 1, (h, w, 1)).astype(np.float32) + 0.35 * rng.normal(0, 1, (h, w, 3)).astype(np.float32)
    n_img = Image.fromarray(np.clip(n[..., 0] * 40 + 128, 0, 255).astype(np.uint8))
    soft = (np.asarray(n_img.filter(ImageFilter.GaussianBlur(0.6)), dtype=np.float32) - 128) / 40
    n = 0.5 * n + 0.5 * soft[..., None]
    lum = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    amount = grain * (0.010 + 0.016 * (1 - np.clip(lum, 0, 1)))[..., None]
    a = a + n * amount

    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8))


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    finish(Image.open(src), seed).save(dst)
