// Neck (dasteh): rounded D-section neck wood, the fingerboard of two bone strips with a
// dark wood strip between them, and the bone nut.
import * as THREE from 'three';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { NECK } from '../dimensions.js';
import { lerp, clamp, loft, dSection } from './util.js';

const FB = NECK.fingerboard;
export const NECK_TOP_Z = NECK.topZ;
export const BOARD_TOP_Z = NECK.topZ + FB.thickness;

const along = (y) => clamp((y - NECK.bottomY) / (NECK.nutY - NECK.bottomY), 0, 1);
export const neckHalfWidth = (y) => lerp(NECK.widthAtBody, NECK.widthAtNut, along(y)) / 2;
export const neckDepth = (y) => lerp(NECK.depthAtBody, NECK.depthAtNut, along(y));

// Cross-section of the neck wood at y, optionally grown outward by `off` (for fret wraps)
// and deepened by `extra` (where the heel thickens the back).
export function neckSection(y, { off = 0, extra = 0, top = NECK_TOP_Z, closeTop = false, nFillet = 6, nBack = 40 } = {}) {
  return dSection(
    neckHalfWidth(y) + off, top + off, neckDepth(y) + extra + (top - NECK_TOP_Z) + 2 * off,
    NECK.cornerRadius + off, nFillet, nBack, NECK.sectionExponent, closeTop,
  );
}

function capAt(y, pts, flip) {
  const shape = new THREE.Shape(pts.map(([x, z]) => new THREE.Vector2(x, z)));
  const g = new THREE.ShapeGeometry(shape);
  // shape lies in x–y; turn it into the x–z plane at height y
  g.rotateX(Math.PI / 2);
  if (flip) g.scale(1, 1, -1);
  g.translate(0, y, 0);
  return g;
}

export function buildNeck(materials) {
  const group = new THREE.Group();
  group.name = 'neck';

  // Neck wood, from the end of the fingerboard on the body up into the head
  const y0 = NECK.boardEndY, y1 = NECK.nutY + 0.4;
  const rows = [];
  for (let j = 0; j <= 80; j++) {
    const y = lerp(y0, y1, j / 80);
    rows.push({ y, pts: neckSection(y, { closeTop: true }) });
  }
  const wood = new THREE.Mesh(loft(rows, { closed: true, vScale: 6 }), materials.lightWood);
  wood.name = 'neckWood';
  wood.castShadow = wood.receiveShadow = true;
  group.add(wood);
  const cap = new THREE.Mesh(capAt(y0, neckSection(y0, { closeTop: true })), materials.lightWood);
  cap.name = 'neckEnd';
  group.add(cap);

  // Fingerboard: three strips with softened edges, tapering with the neck
  const b = FB.bevel, c = FB.centreStrip / 2;
  const yb = NECK.boardEndY, yt = NECK.nutY;
  const strip = (xOuterB, xInnerB, xOuterT, xInnerT) => {
    const s = new THREE.Shape([
      new THREE.Vector2(xOuterB, yb + b), new THREE.Vector2(xInnerB, yb + b),
      new THREE.Vector2(xInnerT, yt - b), new THREE.Vector2(xOuterT, yt - b),
    ]);
    const g = new THREE.ExtrudeGeometry(s, { depth: FB.thickness - 2 * b, bevelEnabled: true, bevelThickness: b, bevelSize: b, bevelSegments: 2, curveSegments: 1 });
    g.translate(0, 0, NECK_TOP_Z + b);
    return g;
  };
  const hwB = neckHalfWidth(yb) - b, hwT = neckHalfWidth(yt) - b;
  const boneL = new THREE.Mesh(strip(-hwB, -c - b, -hwT, -c - b), materials.bone);
  const boneR = new THREE.Mesh(strip(hwB, c + b, hwT, c + b), materials.bone);
  const centre = new THREE.Mesh(strip(-c + b, c - b, -c + b, c - b), materials.boardWood);
  [boneL, boneR, centre].forEach((m, i) => {
    m.name = ['boardBoneLeft', 'boardBoneRight', 'boardCentre'][i];
    m.castShadow = m.receiveShadow = true;
    group.add(m);
  });

  // Nut: a rounded bone block across the top of the fingerboard
  const nut = new THREE.Mesh(
    new RoundedBoxGeometry(neckHalfWidth(NECK.nutY) * 2, NECK.nut.length, NECK.nut.height, 3, NECK.nut.radius),
    materials.boneSmall,
  );
  nut.position.set(0, NECK.nutY - NECK.nut.length / 2, BOARD_TOP_Z + NECK.nut.height / 2);
  nut.name = 'nut';
  nut.castShadow = true;
  group.add(nut);

  return group;
}

// Where the strings cross the nut (used by the strings in phase 4).
export const NUT_TOP = { y: NECK.nutY - NECK.nut.length / 2, z: BOARD_TOP_Z + NECK.nut.height };
