"""Side-by-side check of one extracted frame against its reference panel.
Usage: python3 preview.py NN  ->  frameNN-preview.png (reference left, frame right)
"""
import sys
from pathlib import Path

from PIL import Image, ImageEnhance

from extract import HERE, PANELS

index = int(sys.argv[1])
ref = Image.open(HERE / 'reference.webp').convert('RGB').crop(PANELS[index])
frame = Image.open(HERE / 'frames' / f'{index:02d}.webp')
w, h = ref.size
sheet = Image.new('RGB', (w * 2 + 10, h), 'white')
sheet.paste(ref, (0, 0))
sheet.paste(frame, (w + 10, 0))
sheet.resize((sheet.width * 2, sheet.height * 2), Image.LANCZOS).save(HERE / f'frame{index:02d}-preview.png')

# Brightened close-up of the caption area, to spot leftover text
if len(sys.argv) > 2:
    crop = frame.crop((0, 0, w, 90)).resize((w * 4, 360), Image.NEAREST)
    ImageEnhance.Brightness(crop).enhance(4).save(sys.argv[2])
