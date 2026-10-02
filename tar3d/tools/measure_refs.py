"""Measure silhouette ratios from the reference photos (phase 1, section 1.1 of the spec).

The reference photos are not stored in the repository (they belong to their owners).
Pass their paths on the command line:

    python3 tar3d/tools/measure_refs.py --front F1.webp --body R4.jpg --side R6.jpg --head R5.jpg

Prints per-row widths and the ratios recorded in docs/tar-3d/SPEC.md, section 5.
Needs Pillow and NumPy.
"""
import argparse

import numpy as np
from PIL import Image


def silhouette(path, dark_background):
    a = np.asarray(Image.open(path).convert('RGB')).astype(int)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    if dark_background:
        lum = (r + g + b) / 3
        bg = np.median(np.concatenate([lum[:, :150], lum[:, -150:]], 1), 1)[:, None]
        m = ((r - b) > 6) | (lum > bg + 45) | (lum < bg * 0.45)
    else:
        m = (a.min(2) < 215) | ((a.max(2) - a.min(2)) > 25)
        m[:200, :230] = False  # watermark corner
    return m


def widths(m, rows):
    out = []
    for y in rows:
        xs = np.where(m[y])[0]
        out.append(int(xs.max() - xs.min()) if len(xs) else 0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--front', help='full front photo on a dark background (F1)')
    ap.add_argument('--body', help='body from the front on white (R4)')
    ap.add_argument('--side', help='three-quarter rear view on white (R6)')
    args = ap.parse_args()

    if args.front:
        m = silhouette(args.front, True)
        ys = np.where(m.any(1))[0]
        top, bottom = ys.min(), ys.max()
        w = widths(m, range(top, bottom))
        print('F1 total length px', bottom - top, 'widest px', max(w))
    if args.body:
        m = silhouette(args.body, False)
        for y in range(0, m.shape[0], 25):
            print('R4 row', y, 'width', widths(m, [y])[0])
    if args.side:
        m = silhouette(args.side, False)
        for y in range(0, m.shape[0], 25):
            print('R6 row', y, 'width', widths(m, [y])[0])


if __name__ == '__main__':
    main()
