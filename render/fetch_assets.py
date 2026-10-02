"""Downloads the CC0 assets used by the render (spec section 15) into render/assets/.

All files are from Poly Haven (https://polyhaven.com), released under CC0 (public domain):
  - Ash Veneer: scanned ring-porous wood, used for the colour, pores and fine detail of the wood
  - Brown Photostudio 02: HDRI of a warm interior studio with windows, for soft room light

    python3 render/fetch_assets.py
"""
import json
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parent / 'assets'
TEXTURES = {'ash_veneer': ['Diffuse', 'Rough', 'nor_gl']}
HDRIS = {'brown_photostudio_02': '2k'}


HEADERS = {'User-Agent': 'tar3d-render/1.0 (shit-idea1 project)'}  # Poly Haven rejects anonymous clients


def fetch(url, timeout=120):
    return urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=timeout)


def get(url, dest):
    if dest.exists():
        return
    print('downloading', url)
    with fetch(url) as r:
        dest.write_bytes(r.read())


def main():
    OUT.mkdir(exist_ok=True)
    for asset, maps in TEXTURES.items():
        files = json.load(fetch(f'https://api.polyhaven.com/files/{asset}', 60))
        for m in maps:
            url = files[m]['2k']['jpg']['url']
            get(url, OUT / url.rsplit('/', 1)[1])
    for asset, res in HDRIS.items():
        files = json.load(fetch(f'https://api.polyhaven.com/files/{asset}', 60))
        url = files['hdri'][res]['hdr']['url']
        get(url, OUT / url.rsplit('/', 1)[1])
    for p in sorted(OUT.iterdir()):
        print(f'{p.name:40s} {p.stat().st_size // 1024:6d} KB')


if __name__ == '__main__':
    main()
