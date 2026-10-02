// Frets (pardeh): each fret is several turns of thin gut wound round the neck and tied in a
// knot on the bass side (R2). Where the neck already rests on the body and a fret cannot
// pass round the back, its ends are held by small nails in the sides of the neck (R3).
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { BODY, FRETS, NECK } from '../dimensions.js';
import { FRET_Y } from '../frets.js';
import { lerp, seeded } from './util.js';
import { neckHalfWidth, BOARD_TOP_Z, NECK_TOP_Z } from './neck.js';
import { wrapBackZ } from './heel.js';

const R = FRETS.strandDiameter / 2;

// Closed path round the neck (and heel, where it has thickened) at height y, sitting on
// the surface: across the fingerboard, round the rounded corners, and along the back.
function wrapPath(y, dy, wobble) {
  const hw = neckHalfWidth(y) + R;
  const zTop = BOARD_TOP_Z + R;
  const pts = [];
  const n = 40;
  // back, right to left
  for (let i = 0; i <= n; i++) {
    const x = lerp(hw * 0.995, -hw * 0.995, i / n);
    const z = wrapBackZ(x * (hw - R) / hw, y) - R;
    pts.push(new THREE.Vector3(x, y + dy + wobble(x), z));
  }
  // up the left side to the top
  for (let i = 1; i <= 4; i++) pts.push(new THREE.Vector3(-hw, y + dy, lerp(NECK_TOP_Z, zTop, i / 4)));
  // across the top, left to right
  for (let i = 1; i < 8; i++) pts.push(new THREE.Vector3(lerp(-hw + 0.05, hw - 0.05, i / 8), y + dy, zTop));
  // down the right side
  for (let i = 0; i < 4; i++) pts.push(new THREE.Vector3(hw, y + dy, lerp(zTop, NECK_TOP_Z, i / 4)));
  return new THREE.CatmullRomCurve3(pts, true, 'centripetal');
}

// Open path for a fret over the body: from a nail on the left side, over the top, to a nail
// on the right side.
function openPath(y, dy, zNail) {
  const hw = neckHalfWidth(y) + R;
  const zTop = BOARD_TOP_Z + R;
  const pts = [
    new THREE.Vector3(-hw, y + dy, zNail),
    new THREE.Vector3(-hw, y + dy, lerp(zNail, zTop, 0.6)),
    new THREE.Vector3(-hw + 0.04, y + dy, zTop),
    new THREE.Vector3(0, y + dy, zTop),
    new THREE.Vector3(hw - 0.04, y + dy, zTop),
    new THREE.Vector3(hw, y + dy, lerp(zNail, zTop, 0.6)),
    new THREE.Vector3(hw, y + dy, zNail),
  ];
  return new THREE.CatmullRomCurve3(pts, false, 'centripetal');
}

export function buildFrets(materials, quality) {
  const rand = seeded(7);
  const turns = quality.fretTurns;
  const strandGeos = [], knotGeos = [], nailGeos = [];
  const spacing = FRETS.strandDiameter * 1.05;

  FRET_Y.forEach((y) => {
    const overBody = y < BODY.topY; // the back is inside the body here
    const zNail = BODY.rim.lipHeight + 0.18;
    for (let k = 0; k < turns; k++) {
      const dy = (k - (turns - 1) / 2) * spacing + (rand() - 0.5) * FRETS.jitter;
      // each turn drifts a little across the back, as hand-wound gut does
      const tilt = (rand() - 0.5) * 0.06, bow = (rand() - 0.5) * 0.04;
      const wobble = (x) => tilt * x + bow * (1 - x * x);
      const curve = overBody ? openPath(y, dy, zNail) : wrapPath(y, dy, wobble);
      strandGeos.push(new THREE.TubeGeometry(curve, overBody ? 24 : 72, R, 4, !overBody));
    }

    const hw = neckHalfWidth(y);
    if (overBody) {
      // nail heads on both sides, driven into the sides of the neck
      [-1, 1].forEach((side) => {
        const head = new THREE.CylinderGeometry(FRETS.nailHead, FRETS.nailHead, 0.04, 12);
        head.rotateZ(Math.PI / 2);
        head.translate(side * (hw + R * 2 + 0.02), y, zNail);
        nailGeos.push(head);
      });
    } else {
      // knot on the bass (left) side, just under the fingerboard, with two short tails
      const kx = -(hw + R * 1.5), kz = NECK_TOP_Z - 0.25;
      const knot = new THREE.SphereGeometry(FRETS.knotRadius, 10, 8);
      knot.scale(0.7, 1.25, 1);
      knot.translate(kx, y, kz);
      knotGeos.push(knot);
      [-1, 1].forEach((s) => {
        const tail = new THREE.CatmullRomCurve3([
          new THREE.Vector3(kx, y, kz),
          new THREE.Vector3(kx - 0.03, y + s * 0.08, kz - FRETS.tailLength * 0.5),
          new THREE.Vector3(kx - 0.02, y + s * 0.14, kz - FRETS.tailLength),
        ]);
        knotGeos.push(new THREE.TubeGeometry(tail, 6, R * 0.9, 4, false));
      });
    }
  });

  const group = new THREE.Group();
  group.name = 'frets';
  const strands = new THREE.Mesh(mergeGeometries(strandGeos), materials.gut);
  strands.name = 'fretStrands';
  strands.castShadow = true;
  const knots = new THREE.Mesh(mergeGeometries(knotGeos), materials.gut);
  knots.name = 'fretKnots';
  group.add(strands, knots);
  if (nailGeos.length) {
    const nails = new THREE.Mesh(mergeGeometries(nailGeos), materials.metal);
    nails.name = 'fretNails';
    group.add(nails);
  }
  return group;
}
