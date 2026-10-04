"""Put the extracted frames (frames/NN.webp) on one fixed camera.

Each storyboard panel was framed a little differently, so played in order the
picture jumps. This script tracks the instrument's body from frame to frame
(template match with a rotation search, since the body tips ~5° per frame),
then shifts every frame so the body centre lands on the same canvas point.
The horizon sits at the same height relative to the body in every panel, so
this also steadies the background.

The backdrop/carpet brightness is matched across frames so the sequence does
not flicker. Areas a panel does not cover are filled from the frame itself:
the carpet by tiling the clean strip beside the gap, the backdrop with its
own colour.

Usage: python3 align.py   ->  aligned/NN.webp (all the same size)
"""
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent
COUNT = 17

# Body (both bowls) in frame 00: centre and box size, in pixels
BODY_CENTRE = (82.0, 365.0)
BODY_SIZE = (98, 174)

# Canvas extent around the body centre: room for the head in frame 00 (top)
# and for the neck lying on the floor in frame 16 (right)
LEFT, RIGHT, TOP, BOTTOM = 70, 172, 340, 140
HORIZON = -45  # horizon height relative to the body centre
FEATHER = 6


def gray(image):
    return cv2.GaussianBlur(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (3, 3), 0).astype(np.float32)


def track(frames):
    """Body centre and tilt (degrees) in each frame, following it from the previous frame."""
    cx, cy = BODY_CENTRE
    w, h = BODY_SIZE
    centres = [(cx, cy)]
    tilts = [0.0]
    tilt = 0.0
    pad = 60
    for prev, cur in zip(frames, frames[1:]):
        gp, gc = gray(prev), gray(cur)
        x0, y0 = max(0, int(cx - w / 2)), max(0, int(cy - h / 2))
        template = gp[y0:y0 + h, x0:x0 + w]
        th, tw = template.shape
        mask = np.zeros_like(template)
        cv2.ellipse(mask, (tw // 2, th // 2), (int(tw * 0.45), int(th * 0.47)), 0, 0, 360, 1, -1)
        best = None
        for turn in np.arange(-2, 12.1, 0.5):
            # Undo the extra tilt of the current frame before matching
            m = cv2.getRotationMatrix2D((cx, cy), turn, 1.0)
            m[:, 2] += pad
            warped = cv2.warpAffine(gc, m, (gc.shape[1] + 2 * pad, gc.shape[0] + 2 * pad),
                                    borderMode=cv2.BORDER_REPLICATE)
            result = cv2.matchTemplate(warped, template, cv2.TM_CCORR_NORMED, mask=mask)
            _, score, _, loc = cv2.minMaxLoc(result)
            if best is None or score > best[0]:
                best = (score, loc, m, turn)
        _, loc, m, turn = best
        tilt += turn
        tilts.append(float(tilt))
        point = np.array([loc[0] + tw / 2, loc[1] + th / 2, 1.0])
        cx, cy = cv2.invertAffineTransform(m) @ point
        centres.append((float(cx), float(cy)))
    return centres, tilts


TRIM = 3  # panel edges carry the storyboard's separator lines


def place(frame, centre):
    """Shift the frame onto the canvas; returns image and coverage mask."""
    width, height = LEFT + RIGHT, TOP + BOTTOM
    frame = frame[TRIM:-TRIM, TRIM:-TRIM]
    centre = (centre[0] - TRIM, centre[1] - TRIM)
    shift = np.float32([[1, 0, LEFT - centre[0]], [0, 1, TOP - centre[1]]])
    image = cv2.warpAffine(frame, shift, (width, height), flags=cv2.INTER_LANCZOS4,
                           borderMode=cv2.BORDER_CONSTANT)
    covered = cv2.warpAffine(np.ones(frame.shape[:2], np.float32), shift, (width, height),
                             flags=cv2.INTER_LINEAR, borderValue=0)
    return image, covered


SOURCE = 36  # width of the clean carpet strip repeated into a gap


def fill(image, covered, tilt):
    """Fill what the panel does not cover from the frame itself: the carpet
    by ping-pong tiling the clean strip next to the gap, the backdrop with
    its own colour, the bottom rows by repeating the last real row."""
    ok = covered > 0.99
    out = image.astype(np.float32).copy()
    horizon = TOP + HORIZON
    height, width = ok.shape

    row = TOP + 60  # carpet row below the body: finds where real pixels end
    real = np.nonzero(ok[row])[0]
    start, end = real[0], real[-1] + 1
    # Keep the strip clear of the body, which reaches further right as it tips
    body_right = LEFT + BODY_SIZE[0] / 2 + 8 + 50 * np.sin(np.radians(tilt))
    size = int(np.clip(end - body_right, 8, SOURCE))
    source = out[:, end - size:end].copy()
    for x in range(end, width):
        k = (x - end) // size
        offset = (x - end) % size
        out[:, x] = source[:, size - 1 - offset] if k % 2 == 0 else source[:, offset]
    # Around the horizon the carpet is out of focus but the neck and dust may
    # sit there: use each row's median colour instead of tiled detail
    carpet_cols = slice(max(int(body_right), start), end)
    band_end = min(horizon + 30, height)
    for y in range(horizon - 14, band_end):
        # Lower percentile: the neck is lighter than the blurred carpet/backdrop
        smooth = np.percentile(out[y, carpet_cols], 30, axis=0)
        blend = np.clip((band_end - y) / 12, 0, 1)  # fade into tiled detail below
        out[y, end:] = smooth * blend + out[y, end:] * (1 - blend)
    ok_cols = np.zeros_like(ok)
    ok_cols[:, start:end] = True

    top_rows = np.nonzero(ok[:, start + 2])[0]
    first, last = top_rows[0], top_rows[-1]
    out[last + 1:] = out[last]
    backdrop = np.median(out[first:horizon - 40, start:start + 30].reshape(-1, 3), axis=0)
    out[:first] = backdrop

    # Above the horizon the tiled strip may hold the neck: use the backdrop
    rows = np.arange(height, dtype=np.float32)[:, None, None]
    carpet = np.clip((rows - (horizon - 14)) / 20, 0, 1)
    tiled = ~ok
    tiled[:first] = False
    out[tiled] = (out * carpet + backdrop * (1 - carpet))[tiled]

    soft = cv2.GaussianBlur(ok.astype(np.float32), (0, 0), FEATHER)
    soft = np.minimum(soft, ok)[:, :, None]
    blended = image.astype(np.float32) * soft + out * (1 - soft)
    return np.where(ok[:, :, None] & (soft > 0.999), image, blended)


def match_tone(images, coverage):
    """Match backdrop and carpet levels of every frame to the sequence average."""
    horizon = TOP + HORIZON
    lows, highs = [], []
    for img, cov in zip(images, coverage):
        ok = cov > 0.99
        top, bottom = ok.copy(), ok.copy()
        top[horizon - 40:] = False
        top[:, 40:] = False  # left strip: backdrop only, away from the neck
        bottom[:-60] = False
        lows.append(img[top].mean(axis=0))
        highs.append(img[bottom].mean(axis=0))
    low_t, high_t = np.mean(lows, axis=0), np.mean(highs, axis=0)
    out = []
    for img, low, high in zip(images, lows, highs):
        gain = (high_t - low_t) / np.maximum(high - low, 1e-3)
        out.append((img.astype(np.float32) - low) * gain + low_t)
    return out


def main():
    frames = [cv2.imread(str(HERE / 'frames' / f'{i:02d}.webp')) for i in range(COUNT)]
    centres, tilts = track(frames)
    placed = [place(frame, centre) for frame, centre in zip(frames, centres)]
    coverage = [cov for _, cov in placed]
    images = match_tone([img for img, _ in placed], coverage)
    images = [fill(img, cov, tilt) for img, cov, tilt in zip(images, coverage, tilts)]
    out_dir = HERE / 'aligned'
    out_dir.mkdir(exist_ok=True)
    for i, (img, centre) in enumerate(zip(images, centres)):
        path = out_dir / f'{i:02d}.webp'
        cv2.imwrite(str(path), np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_WEBP_QUALITY, 95])
        print(path.name, 'body centre', tuple(round(v, 1) for v in centre))


if __name__ == '__main__':
    main()
