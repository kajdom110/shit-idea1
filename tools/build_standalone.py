"""Build a single-file test copy of the landing page that opens straight from
disk (double-click, no server): CSS, JS and all frames are inlined, the
frames as base64 data URIs.

Usage: python3 tools/build_standalone.py  ->  dist/landing-standalone.html
"""
import base64
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRAMES = sorted((ROOT / 'assets' / 'saz' / 'seq').glob('*.webp'))


def main():
    html = (ROOT / 'landing.html').read_text(encoding='utf-8')
    css = (ROOT / 'landing.css').read_text(encoding='utf-8')
    js = (ROOT / 'landing.js').read_text(encoding='utf-8')
    frames = ['data:image/webp;base64,' + base64.b64encode(f.read_bytes()).decode() for f in FRAMES]

    html = html.replace('  <link rel="preload" as="image" href="assets/saz/seq/000.webp">\n', '')
    html = html.replace('src="assets/saz/seq/000.webp"', 'src="' + frames[0] + '"')
    html = html.replace('<link rel="stylesheet" href="landing.css">', '<style>\n' + css + '</style>')
    html = html.replace('<script src="landing.js"></script>',
                        '<script>window.SAZ_FRAMES = ' + json.dumps(frames) + ';</script>\n'
                        '  <script>\n' + js + '</script>')

    out = ROOT / 'dist' / 'landing-standalone.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text(html, encoding='utf-8')
    print(out, f'{out.stat().st_size / 1e6:.1f} MB', len(frames), 'frames')


if __name__ == '__main__':
    main()
