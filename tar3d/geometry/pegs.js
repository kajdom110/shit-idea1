// Pegs (goushi): six turned pegs, three each side and staggered (R5). Each peg is one lathe
// profile — tapered shaft, collar, narrow neck, flare and a large knob with two cut grooves —
// plus the shaft running through the head, its tip just showing on the far side.
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { HEAD, PEGS, TOTAL_LENGTH } from '../dimensions.js';
import { HEAD_MID_Z } from './head.js';

// Profile along the peg axis: [distance from the head wall, radius], ending at the knob tip.
// Scaled so the last point lands on PEGS.reach and the knob on PEGS.knobDiameter.
const PROFILE = [
  [0, 0.5], [1.45, 0.46], [1.5, 0.62], [1.55, 0.8], [1.72, 0.8], [1.8, 0.6], [1.86, 0.45],
  [2.2, 0.42], [2.36, 0.55], [2.56, 0.9], [2.76, 1.25], [3.1, 1.52], [3.6, 1.6], [4.08, 1.58],
  [4.18, 1.5], [4.26, 1.58], [4.56, 1.49], [4.64, 1.39], [4.72, 1.45], [4.94, 1.2],
  [5.08, 0.82], [5.17, 0.42], [5.2, 0],
];

export const pegY = (p) => TOTAL_LENGTH - p.at * HEAD.height;

function pegGeometry() {
  const s = PEGS.reach / 5.2, r = PEGS.knobDiameter / 3.2;
  const pts = PROFILE.map(([u, rad]) => new THREE.Vector2(Math.max(rad * (u > 2.3 ? r : 1), 0.001), u * s));
  const knob = new THREE.LatheGeometry(pts, 40);
  // Shaft through the head: from the wall back across the slot to just past the far wall.
  const through = HEAD.width + 0.25;
  const shaft = new THREE.CylinderGeometry(PEGS.shaftDiameter / 2, PEGS.shaftTipDiameter / 2, through, 20, 1, false);
  shaft.translate(0, -through / 2, 0);
  return mergeGeometries([knob, shaft]);
}

export function buildPegs(materials) {
  const group = new THREE.Group();
  group.name = 'pegs';
  const geo = pegGeometry();
  PEGS.layout.forEach((p, i) => {
    const m = new THREE.Mesh(geo, materials.pegWood);
    // lathe axis is +y; turn it to point out of the head on this peg's side
    m.rotation.z = -p.side * Math.PI / 2;
    m.position.set(p.side * HEAD.width / 2, pegY(p), HEAD_MID_Z);
    // each peg sits at its own slight turn, as tuned pegs do
    m.rotation.x = i * 0.9;
    m.name = 'peg' + p.string;
    m.castShadow = m.receiveShadow = true;
    group.add(m);
  });
  return group;
}

// Axis of each peg in instrument space, for the strings: x runs across the head.
export const pegAxis = (p) => ({ y: pegY(p), z: HEAD_MID_Z, r: PEGS.shaftDiameter / 2 });
