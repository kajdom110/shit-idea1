"""Writes web/frames.json for the player (R5): for each of the scroll frames, the instrument's
approximate turn (yaw) and tilt (pitch), so a drag can start from the nearest frame of the
rotation sheet; and where each caption sits on the scroll. Mirrors TIMELINE in build_scene.py.

    python3 render/make_web_data.py
"""
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
KF = json.loads((HERE / 'build/scenes.json').read_text())['keyframes']
PLIST = json.loads((HERE / 'build/plist.json').read_text())  # scroll position of each frame
TOTAL = len(PLIST)
SCENES_END, FRONT, FALL0, FALL1 = 0.60, 0.64, 0.66, 0.82


def ease(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def scene_pose(p):
    i = 0
    while i < len(KF) - 2 and p > KF[i + 1]['at']:
        i += 1
    a, b = KF[i], KF[i + 1]
    t = ease((p - a['at']) / (b['at'] - a['at']))
    dist = math.exp(math.log(a['dist']) + (math.log(b['dist']) - math.log(a['dist'])) * t)
    return a['yaw'] + (b['yaw'] - a['yaw']) * t, a['pitch'] + (b['pitch'] - a['pitch']) * t, dist


frames = []
for f in range(TOTAL):
    p = PLIST[f]
    if p <= SCENES_END:
        yaw, pitch, dist = scene_pose(p / SCENES_END)
    elif p <= FRONT:
        y0, p0, dist = scene_pose(1.0)
        y1 = round(KF[-1]['yaw'] / 360) * 360
        t = ease((p - SCENES_END) / (FRONT - SCENES_END))
        yaw, pitch = y0 + (y1 - y0) * t, p0 * (1 - t)
    else:
        dist = 0  # falling and zooming: no matching sheet scale
        t = min(1.0, max(0.0, (p - FALL0) / (FALL1 - FALL0)))
        yaw, pitch = 0.0, -90 * min(1.0, 1.02 * (t / 0.82) ** 2) if t < 0.82 else -90.0
    frames.append([round(yaw % 360, 1), round(pitch, 1), round(dist)])

captions = [round(k['at'] * SCENES_END, 4) for k in KF if k['caption'] != 0 or k['at'] == 0]
captions = sorted(set(captions)) + [round((FALL1 + 1) / 2, 4)]  # last: the zoom onto the face
(HERE / 'web/frames.json').write_text(json.dumps({
    'count': TOTAL, 'p': PLIST, 'frames': frames, 'captions': captions,
    'sheet': {'yawStep': 15, 'pitches': [-60, -30, 0, 30, 60], 'dist': 250},
}))
print(captions)
