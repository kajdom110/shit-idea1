// Cinematic scroll scenes. Each keyframe is a pose of the instrument (turn and tilt), the point
// of the instrument the camera looks at, the camera distance and elevation, exposure and depth
// of field. Between keyframes the motion eases out of one pose and into the next, resting a
// moment on each; scrolling back plays exactly the same path in reverse.
import * as THREE from 'three';
import { PIVOT } from './dimensions.js';

const C = [PIVOT.x, PIVOT.y, PIVOT.z]; // whole instrument

// at: scroll position 0…1. yaw/pitch in degrees: yaw turns about the vertical (negative = to
// the left), pitch tips the instrument towards the camera. target: point on the instrument (cm).
export const KEYFRAMES = [
  { at: 0.0, caption: 0, yaw: -35, pitch: 6, target: C, dist: 330, elev: 2, exposure: 0.12 },
  { at: 0.07, caption: 0, yaw: -35, pitch: 6, target: C, dist: 310, elev: 2, exposure: 1 },
  { at: 0.22, caption: 1, yaw: 0, pitch: 0, target: C, dist: 265, elev: 1, exposure: 1 },
  { at: 0.38, caption: 2, yaw: -90, pitch: 0, target: [0, 20, -8], dist: 150, elev: 3, exposure: 1 },
  { at: 0.54, caption: 3, yaw: -180, pitch: -15, target: [0, 27, -12], dist: 125, elev: 4, exposure: 1 },
  { at: 0.7, caption: 4, yaw: -320, pitch: 22, target: [0, 60, 0], dist: 95, elev: 3, exposure: 1 },
  { at: 0.86, caption: 5, yaw: -380, pitch: 8, target: [0, 88, -0.8], dist: 48, elev: 4, exposure: 1, aperture: 0.0003 },
  { at: 1.0, caption: 6, yaw: -395, pitch: 5, target: C, dist: 300, elev: 2, exposure: 1 },
];

const deg = THREE.MathUtils.degToRad;
const X = new THREE.Vector3(1, 0, 0), Y = new THREE.Vector3(0, 1, 0);
const quats = KEYFRAMES.map((k) => {
  const qx = new THREE.Quaternion().setFromAxisAngle(X, deg(k.pitch));
  const qy = new THREE.Quaternion().setFromAxisAngle(Y, deg(k.yaw));
  return qx.multiply(qy); // turn first, then tip towards the camera
});

// Ease that rests at both ends: the first and last 15% of each stretch hold the pose.
function ease(t) {
  const u = THREE.MathUtils.clamp((t - 0.15) / 0.7, 0, 1);
  return u * u * u * (u * (u * 6 - 15) + 10);
}

export function sampleScroll(p) {
  p = THREE.MathUtils.clamp(p, 0, 1);
  let i = 0;
  while (i < KEYFRAMES.length - 2 && p > KEYFRAMES[i + 1].at) i++;
  const a = KEYFRAMES[i], b = KEYFRAMES[i + 1];
  const t = ease((p - a.at) / (b.at - a.at));
  const lerp = THREE.MathUtils.lerp;
  return {
    quaternion: quats[i].clone().slerp(quats[i + 1], t),
    target: new THREE.Vector3(...a.target).lerp(new THREE.Vector3(...b.target), t),
    dist: Math.exp(lerp(Math.log(a.dist), Math.log(b.dist), t)),
    elev: deg(lerp(a.elev, b.elev, t)),
    exposure: lerp(a.exposure, b.exposure, t),
    aperture: lerp(a.aperture || 0, b.aperture || 0, t),
    // how strongly each caption shows: full while its pose rests, fading through the move
    captions: KEYFRAMES.reduce((acc, k, j) => {
      const w = j === i ? 1 - t : j === i + 1 ? t : 0;
      acc[k.caption] = Math.max(acc[k.caption] || 0, w);
      return acc;
    }, {}),
  };
}
