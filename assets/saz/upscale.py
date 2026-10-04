"""Upscale the aligned frames 4x with Real-ESRGAN (free, open source).

Model: RealESRGAN_x4plus (https://github.com/xinntao/Real-ESRGAN), loaded
with spandrel and run on the CPU. Download the weights next to this script
or pass their path with --weights.

Usage: python3 upscale.py [--weights PATH] NN [NN ...]  ->  hd/NN.webp
"""
import argparse
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from spandrel import ModelLoader

HERE = Path(__file__).parent


def upscale(model, image):
    x = torch.from_numpy(np.asarray(image, dtype=np.float32) / 255).permute(2, 0, 1)[None]
    with torch.no_grad():
        y = model(x)
    y = y[0].clamp(0, 1).permute(1, 2, 0).numpy()
    return Image.fromarray((y * 255).round().astype(np.uint8))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--weights', default=str(HERE / 'RealESRGAN_x4plus.pth'))
    parser.add_argument('frames', nargs='+', type=int)
    args = parser.parse_args()

    torch.set_num_threads(torch.get_num_threads())
    model = ModelLoader().load_from_file(args.weights).eval()
    out_dir = HERE / 'hd'
    out_dir.mkdir(exist_ok=True)
    for index in args.frames:
        image = Image.open(HERE / 'aligned' / f'{index:02d}.webp').convert('RGB')
        result = upscale(model, image)
        path = out_dir / f'{index:02d}.webp'
        result.save(path, quality=92)
        print(path.name, result.size)


if __name__ == '__main__':
    main()
