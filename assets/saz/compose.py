"""Build the final scroll frames on one unchanging carpet.

1. plate:  the approved HD frame 00 with the instrument (and its contact
           shadow) removed by LaMa inpainting -> plate.webp. Every frame uses
           this same background, so the carpet never changes.
2. frames: each aligned frame is upscaled 4x (Real-ESRGAN, see upscale.py),
           the instrument is cut out with rembg (isnet-general-use) and laid
           on the plate with a soft contact shadow -> final/NN.webp.
           Frames 14-16 get dust rebuilt along the impact line (the panels'
           carpets differ, so it cannot be lifted from them).

Free models used (weights are not committed; pass their paths):
  RealESRGAN_x4plus.pth  https://github.com/xinntao/Real-ESRGAN
  big-lama.pt            https://github.com/Sanster/models (LaMa)
  isnet-general-use      downloaded automatically by rembg

Usage: python3 compose.py --esrgan PATH --lama PATH plate
       python3 compose.py --esrgan PATH --lama PATH NN [NN ...]
"""
import argparse
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from rembg import new_session, remove
from spandrel import ModelLoader

from upscale import upscale

HERE = Path(__file__).parent
HD = HERE / 'hd'
FINAL = HERE / 'final'
PLATE = HERE / 'plate.webp'

PAD_LEFT = 72  # px of carpet/backdrop added on the left so the instrument is not on the edge
SHADOW_STRENGTH = 0.55
SHADOW_BLUR = 22  # px at HD size
SHADOW_DROP = 14  # shadow sits slightly below the instrument


def to_float(image):
    return np.asarray(image.convert('RGB'), dtype=np.float32) / 255


def to_image(array):
    return Image.fromarray((np.clip(array, 0, 1) * 255).round().astype(np.uint8))


def hd_frame(index, esrgan):
    """4x upscale of the aligned frame, cached in hd/."""
    path = HD / f'{index:02d}.webp'
    if not path.exists():
        HD.mkdir(exist_ok=True)
        image = Image.open(HERE / 'aligned' / f'{index:02d}.webp').convert('RGB')
        upscale(esrgan, image).save(path, quality=92)
    return Image.open(path).convert('RGB')


def matte(image, session):
    """Soft alpha of the instrument, pulled in a little so no old carpet fringes."""
    alpha = np.asarray(remove(image, session=session, only_mask=True), dtype=np.float32) / 255
    alpha = cv2.erode(alpha, np.ones((3, 3), np.uint8))
    return cv2.GaussianBlur(alpha, (0, 0), 0.8)


def build_plate(esrgan, lama, session):
    image = hd_frame(0, esrgan)
    alpha = matte(image, session)
    solid = (alpha > 0.1).astype(np.uint8)
    ys, xs = np.nonzero(solid)
    bottom = ys.max()
    low = xs[ys > bottom - 200]
    hole = cv2.dilate(solid, np.ones((31, 31), np.uint8))
    # The contact shadow under the bowl must go too
    cv2.ellipse(hole, (int(low.mean()), int(bottom)),
                (int((low.max() - low.min()) / 2 + 70), 70), 0, 0, 360, 1, -1)
    x = torch.from_numpy(to_float(image)).permute(2, 0, 1)[None]
    mask = torch.from_numpy(hole.astype(np.float32))[None, None]
    with torch.no_grad():
        plate = lama(x, mask)[0].clamp(0, 1).permute(1, 2, 0).numpy()
        # Outpaint a strip on the left: the panels put the body right at the edge
        wide = np.pad(plate, ((0, 0), (PAD_LEFT, 0), (0, 0)))
        strip = np.zeros(wide.shape[:2], np.float32)
        strip[:, :PAD_LEFT] = 1
        x = torch.from_numpy(wide).permute(2, 0, 1)[None]
        mask = torch.from_numpy(strip)[None, None]
        plate = lama(x, mask)[0].clamp(0, 1).permute(1, 2, 0).numpy()
    plate = smooth_backdrop(plate, np.pad(hole, ((0, 0), (PAD_LEFT, 0)), constant_values=1))
    to_image(plate).save(PLATE, quality=95)
    return plate


def smooth_backdrop(plate, hole):
    """Rebuild the black backdrop as a smooth surface fitted to its real
    pixels, so inpainting leaves no trace of the neck in the dark area."""
    from align import HORIZON, TOP
    horizon = (TOP + HORIZON) * 4
    top = horizon - 40
    region = plate[:top]
    known = ~hole[:top].astype(bool)
    known[:8] = False  # frame edge
    ys, xs = np.mgrid[0:top, 0:plate.shape[1]].astype(np.float32) / 500
    basis = np.stack([np.ones_like(xs), xs, ys, xs * xs, ys * ys, xs * ys], axis=-1)
    coef, *_ = np.linalg.lstsq(basis[known], region[known], rcond=None)
    rng = np.random.default_rng(0)
    smooth = basis @ coef + rng.normal(0, 0.004, region.shape)
    out = plate.copy()
    out[:top] = smooth
    # Blend into the carpet over the last rows above the horizon
    ramp = np.clip((np.arange(top - 80, top) - (top - 80)) / 80, 0, 1)[:, None, None]
    out[top - 80:top] = smooth[-80:] * (1 - ramp) + plate[top - 80:top] * ramp
    return out


def contact_shadow(alpha, horizon):
    shadow = np.roll(alpha, SHADOW_DROP, axis=0)
    shadow = cv2.GaussianBlur(shadow, (0, 0), SHADOW_BLUR)
    shadow[:horizon] = 0  # nothing to shade on the black backdrop
    return np.clip(shadow * 1.6, 0, 1) * SHADOW_STRENGTH


# Dust kicked up by the impact, only in the last three frames:
# (haze strength, haze spread px, haze height px, particles, max rise px,
#  how far the haze rolls out to the right px)
DUST = {14: (0.80, 80, 110, 420, 260, 320), 15: (0.75, 120, 150, 380, 340, 440), 16: (0.55, 150, 90, 160, 120, 360)}
DUST_COLOUR = np.array([0.80, 0.72, 0.60], np.float32)


def noise(shape, rng):
    """Cloudy texture in 0..1 from blurred random noise at a few scales."""
    total = np.zeros(shape, np.float32)
    for sigma, weight in ((40, 0.5), (14, 0.3), (4, 0.2)):
        layer = cv2.GaussianBlur(rng.random(shape).astype(np.float32), (0, 0), sigma)
        layer = (layer - layer.min()) / max(layer.max() - layer.min(), 1e-6)
        total += layer * weight
    return total


def dust(index, alpha, horizon):
    """Haze along the line where the instrument meets the carpet, plus particles."""
    strength, spread, rise, count, max_rise, reach = DUST[index]
    rng = np.random.default_rng(index)
    height, width = alpha.shape
    solid = alpha > 0.5
    has = solid.any(axis=0)
    bottom = np.where(has, height - 1 - np.argmax(solid[::-1], axis=0), 0)
    contact = has & (bottom > horizon + 40)  # columns resting near the floor

    seed = np.zeros(alpha.shape, np.float32)
    for x in np.nonzero(contact)[0]:
        seed[max(bottom[x] - rise, 0):min(bottom[x] + rise // 3, height), x] = 1
    # The puff also rolls out across the carpet to the right
    floor = int(np.median(bottom[contact]))
    last = np.nonzero(contact)[0].max()
    seed[max(floor - rise, 0):min(floor + rise // 4, height), last:min(last + reach, width)] = 1
    haze = cv2.GaussianBlur(seed, (0, 0), spread / 2)
    haze = haze / max(haze.max(), 1e-6)
    # ...thinning out with distance from the impact
    columns = np.arange(width, dtype=np.float32)
    haze *= np.clip(1 - (columns - last) / reach, 0, 1)[None, :] ** 0.6
    haze *= 0.35 + 0.65 * noise(alpha.shape, rng)
    # Fade out towards the horizon instead of a hard edge
    rows = np.arange(height, dtype=np.float32)[:, None]
    haze *= np.clip((rows - (horizon - 20)) / 120, 0, 1)
    haze = np.clip(haze * strength, 0, 1)

    specks = np.zeros(alpha.shape, np.float32)
    xs = np.nonzero(contact)[0]
    for _ in range(count):
        x = rng.choice(xs) + rng.normal(0, spread * 0.6)
        y = bottom[int(np.clip(x, xs.min(), xs.max()))] - rng.exponential(max_rise / 3)
        if 0 <= x < width and 0 <= y < height:
            cv2.circle(specks, (int(x), int(y)), int(rng.integers(1, 4)), float(rng.uniform(0.3, 0.9)), -1)
    specks = cv2.GaussianBlur(specks, (0, 0), 0.8)
    return np.clip(haze, 0, 1), np.clip(specks, 0, 1)


def compose(index, esrgan, session, plate, horizon):
    image = np.pad(to_float(hd_frame(index, esrgan)), ((0, 0), (PAD_LEFT, 0), (0, 0)))
    alpha = np.pad(matte(hd_frame(index, esrgan), session), ((0, 0), (PAD_LEFT, 0)))
    background = plate * (1 - contact_shadow(alpha, horizon))[:, :, None]
    a = alpha[:, :, None]
    out = image * a + background * (1 - a)
    if index in DUST:
        # Dust drifts in front of the carpet and partly over the instrument's base
        haze, specks = dust(index, alpha, horizon)
        d = haze[:, :, None] * (1 - 0.8 * a) + specks[:, :, None] * (1 - 0.85 * a)
        d = np.clip(d, 0, 1)
        out = out * (1 - d) + DUST_COLOUR * d
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--esrgan', required=True)
    parser.add_argument('--lama', required=True)
    parser.add_argument('targets', nargs='+')
    args = parser.parse_args()

    loader = ModelLoader()
    esrgan = loader.load_from_file(args.esrgan).eval()
    session = new_session('isnet-general-use')

    if 'plate' in args.targets or not PLATE.exists():
        lama = loader.load_from_file(args.lama).eval()
        build_plate(esrgan, lama, session)
        print(PLATE.name)
    plate = to_float(Image.open(PLATE))

    from align import HORIZON, TOP
    horizon = (TOP + HORIZON) * 4

    FINAL.mkdir(exist_ok=True)
    for target in args.targets:
        if target == 'plate':
            continue
        index = int(target)
        path = FINAL / f'{index:02d}.webp'
        to_image(compose(index, esrgan, session, plate, horizon)).save(path, quality=92)
        print(path.name)


if __name__ == '__main__':
    main()
