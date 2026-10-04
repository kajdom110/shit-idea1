"""Cut the reference storyboard (reference.webp) into separate frame images.

Each panel is cropped on its own, the "Frame NN / angle" caption is painted
out with the background colour, and the result is saved as frames/NN.webp.
Usage: python3 extract.py 0 [1 2 ...]
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).parent

# Panel boxes (left, top, right, bottom) found from the white separator lines
TOP = [(0, 168), (170, 330), (332, 503), (504, 681), (683, 850),
       (852, 1025), (1027, 1198), (1200, 1370), (1371, 1536)]
BOTTOM = [(0, 179), (181, 359), (361, 531), (533, 711), (713, 894),
          (895, 1087), (1089, 1292), (1294, 1536)]
PANELS = [(l, 0, r, 513) for l, r in TOP] + [(l, 515, r, 1024) for l, r in BOTTOM]

CAPTION = (0, 0, 95, 62)  # caption area inside each panel
# Where the text actually sits ("Frame NN" line, then the angle line);
# kept tight so the pegbox, which can reach into the caption area, is untouched
TEXT_BOXES = [(6, 6, 88, 35), (18, 33, 56, 62)]


def clean_caption(panel):
    px = np.asarray(panel).astype(float) / 255
    l, t, r, b = CAPTION
    region = px[t:b, l:r]
    hi, lo = region.max(axis=2), region.min(axis=2)
    saturation = np.where(hi > 0, (hi - lo) / np.maximum(hi, 1e-6), 0)
    # Caption text is white/grey; the instrument there is saturated wood
    in_boxes = np.zeros(hi.shape, bool)
    for bl, bt, br, bb in TEXT_BOXES:
        in_boxes[bt:bb, bl:br] = True
    instrument = (hi > 0.15) & (saturation >= 0.35)
    near_instrument = np.asarray(Image.fromarray((instrument * 255).astype(np.uint8))
                                 .filter(ImageFilter.MaxFilter(3))) > 0
    text = (hi > 0.07) & (saturation < 0.35) & in_boxes
    mask = Image.fromarray((text * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(7))
    text = (np.asarray(mask) > 0) & in_boxes & ~near_instrument
    background = np.median(region[~text & (hi < 0.12)], axis=0)
    region[text] = background
    px[t:b, l:r] = region
    return Image.fromarray((px * 255).round().astype(np.uint8))


def extract(index):
    sheet = Image.open(HERE / 'reference.webp').convert('RGB')
    panel = clean_caption(sheet.crop(PANELS[index]))
    out = HERE / 'frames' / f'{index:02d}.webp'
    panel.save(out, quality=95)
    return out


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        print(extract(int(arg)))
