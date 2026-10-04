"""Build the smooth, evenly paced scroll sequence from the 17 key frames.

The key frames tilt by uneven steps (2.5° to 12°), so played one per scroll
step the fall speeds up and slows down. Here the rotation (and slight size
change) between neighbouring key frames is measured from the instrument's
outline, and frames are rendered at equal angle steps instead. An
in-between frame rotates the instrument of the key frame before it forward
and that of the key frame after it back to the same angle, around the body
centre, and blends the two; both copies sit in the same pose, so there is
no double image. Everything lands on the fixed carpet plate, with the
contact shadow and, from the impact on, the dust.

Usage: python3 sequence.py [COUNT]  ->  seq/NNN.webp (default 81 frames)
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from rembg import new_session

import align
from compose import DUST, DUST_COLOUR, HD, PAD_LEFT, PLATE, contact_shadow, dust, matte, to_float, to_image

HERE = Path(__file__).parent
OUT = HERE / 'seq'
SCALE = 4  # hd frames are 4x the aligned ones
CENTRE = (align.LEFT * SCALE + PAD_LEFT, align.TOP * SCALE)  # body centre on the HD canvas
HORIZON = (align.TOP + align.HORIZON) * SCALE


def tilts():
    frames = [cv2.imread(str(HERE / 'frames' / f'{i:02d}.webp')) for i in range(align.COUNT)]
    return align.track(frames)[1]


def key_layers(session):
    """Instrument colour, alpha and dust layers of every key frame on the HD canvas."""
    layers = []
    for index in range(align.COUNT):
        image = Image.open(HD / f'{index:02d}.webp').convert('RGB')
        colour = np.pad(to_float(image), ((0, 0), (PAD_LEFT, 0), (0, 0)))
        alpha = np.pad(matte(image, session), ((0, 0), (PAD_LEFT, 0)))
        if index in DUST:
            haze, specks = dust(index, alpha, HORIZON)
        else:
            haze = specks = np.zeros_like(alpha)
        layers.append((colour, alpha, haze, specks))
        print('key', index)
    return layers


def fit_step(alpha0, alpha1, guess):
    """Rotation (clockwise degrees) and scale about the body centre that best
    lays the outline of one key frame on the next. The long neck dominates
    the overlap, so this follows the motion the eye actually sees."""
    small0 = cv2.resize(alpha0, None, fx=0.25, fy=0.25)
    small1 = cv2.resize(alpha1, None, fx=0.25, fy=0.25)
    centre = (CENTRE[0] / 4, CENTRE[1] / 4)
    best = (-1.0, guess, 1.0)
    for degrees in np.arange(max(guess - 6, -2), guess + 8, 0.25):
        for scale in np.arange(0.9, 1.101, 0.02):
            m = cv2.getRotationMatrix2D(centre, -degrees, scale)
            moved = cv2.warpAffine(small0, m, (small0.shape[1], small0.shape[0]))
            overlap = (moved * small1).sum() / ((moved + small1).sum() / 2 + 1e-6)
            if overlap > best[0]:
                best = (overlap, degrees, scale)
    return best[1], best[2]


def rotate(colour, alpha, degrees, scale=1.0):
    """Rotate (clockwise) and scale premultiplied colour and alpha around the body centre."""
    m = cv2.getRotationMatrix2D(CENTRE, -degrees, scale)
    size = (alpha.shape[1], alpha.shape[0])
    premultiplied = cv2.warpAffine(colour * alpha[:, :, None], m, size, flags=cv2.INTER_CUBIC)
    alpha = cv2.warpAffine(alpha, m, size, flags=cv2.INTER_CUBIC)
    return premultiplied, np.clip(alpha, 0, 1)


def frame_at(angle, angles, scales, layers, plate):
    i = int(np.clip(np.searchsorted(angles, angle, side='right') - 1, 0, len(angles) - 2))
    span = angles[i + 1] - angles[i]
    t = float(np.clip((angle - angles[i]) / span, 0, 1)) if span > 0 else 0.0

    c0, a0, h0, s0 = layers[i]
    c1, a1, h1, s1 = layers[i + 1]
    # Interpolate the size change too (the neck foreshortens as it falls)
    p0, a0 = rotate(c0, a0, t * span, scales[i] ** t)
    p1, a1 = rotate(c1, a1, -(1 - t) * span, scales[i] ** (t - 1))
    premultiplied = p0 * (1 - t) + p1 * t
    alpha = a0 * (1 - t) + a1 * t
    colour = premultiplied / np.maximum(alpha, 1e-4)[:, :, None]

    out = plate * (1 - contact_shadow(alpha, HORIZON))[:, :, None]
    a = alpha[:, :, None]
    out = colour * a + out * (1 - a)
    # Dust only rises at the impact (key frame 14): no fade-in before it
    w = t if h0.any() else t ** 6
    haze = h0 * (1 - w) + h1 * w
    specks = s0 * (1 - w) + s1 * w
    d = np.clip(haze[:, :, None] * (1 - 0.8 * a) + specks[:, :, None] * (1 - 0.85 * a), 0, 1)
    return out * (1 - d) + DUST_COLOUR * d


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 81
    body = tilts()
    plate = to_float(Image.open(PLATE))
    layers = key_layers(new_session('isnet-general-use'))
    steps = [fit_step(layers[i][1], layers[i + 1][1], body[i + 1] - body[i]) for i in range(len(layers) - 1)]
    angles = np.concatenate([[0], np.cumsum([d for d, _ in steps])])
    scales = [k for _, k in steps]
    print('key frame angles', [round(float(a), 2) for a in angles])
    print('step scales', [round(float(k), 2) for k in scales])
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob('*.webp'):
        old.unlink()
    for n, angle in enumerate(np.linspace(angles[0], angles[-1], count)):
        to_image(frame_at(angle, angles, scales, layers, plate)).save(OUT / f'{n:03d}.webp', quality=82)
    print(count, 'frames ->', OUT)


if __name__ == '__main__':
    main()
