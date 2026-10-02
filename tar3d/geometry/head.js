// Head (sarpanjeh): a hollow block with an open slot in front, a solid back wall, and
// cusped three-lobed cut-outs at both ends of the slot (R5). Built from two extrusions:
// the back wall, and the frame around the slot.
import * as THREE from 'three';
import { HEAD, NECK, TOTAL_LENGTH } from '../dimensions.js';
import { symmetricShape } from './util.js';
import { BOARD_TOP_Z } from './neck.js';

export const HEAD_FRONT_Z = BOARD_TOP_Z;
export const HEAD_BACK_Z = BOARD_TOP_Z - HEAD.depth;
export const HEAD_MID_Z = (HEAD_FRONT_Z + HEAD_BACK_Z) / 2;
export const SLOT_HALF = HEAD.slot.width / 2;
export const slotRange = [TOTAL_LENGTH - HEAD.slot.bottom, TOTAL_LENGTH - HEAD.slot.top];

// Half-width of the slot at y: straight sides, and at each end a cusp made of one large
// central lobe and two small side lobes.
function slotHalfWidth(y) {
  const [lo, hi] = slotRange;
  const c = HEAD.cusp;
  // d = distance into the cusp from the end of the straight part (0 … c.height)
  const lobes = (d) => {
    let w = d <= 0 ? SLOT_HALF : 0;
    const centre = c.centreRadius * c.centreRadius - Math.pow(d - c.height + c.centreRadius, 2);
    if (centre > 0) w = Math.max(w, Math.sqrt(centre));
    const side = c.sideRadius * c.sideRadius - Math.pow(d - c.sideRadius * 0.6, 2);
    if (side > 0) w = Math.max(w, c.sideOffset + Math.sqrt(side));
    return Math.min(w, SLOT_HALF + 0.02);
  };
  if (y < lo + c.height) return lobes(lo + c.height - y);
  if (y > hi - c.height) return lobes(y - (hi - c.height));
  return SLOT_HALF;
}

function roundedRect(x0, y0, x1, y1, r) {
  const s = new THREE.Shape();
  s.moveTo(x0 + r, y0);
  s.lineTo(x1 - r, y0);
  s.absarc(x1 - r, y0 + r, r, -Math.PI / 2, 0, false);
  s.lineTo(x1, y1 - r);
  s.absarc(x1 - r, y1 - r, r, 0, Math.PI / 2, false);
  s.lineTo(x0 + r, y1);
  s.absarc(x0 + r, y1 - r, r, Math.PI / 2, Math.PI, false);
  s.lineTo(x0, y0 + r);
  s.absarc(x0 + r, y0 + r, r, Math.PI, Math.PI * 1.5, false);
  return s;
}

export function buildHead(materials) {
  const group = new THREE.Group();
  group.name = 'head';
  const hw = HEAD.width / 2, b = HEAD.bevel;
  const y0 = NECK.nutY, y1 = TOTAL_LENGTH;
  const extrudeOpts = (depth) => ({ depth: depth - 2 * b, bevelEnabled: true, bevelThickness: b, bevelSize: b, bevelSegments: 3, curveSegments: 6 });

  // Back wall: the full outline
  const backShape = roundedRect(-hw + b, y0 + b, hw - b, y1 - b, HEAD.cornerRadius);
  // Geometry is moved, not the mesh, so the solid wood pattern lines up across all parts.
  const back = new THREE.Mesh(new THREE.ExtrudeGeometry(backShape, extrudeOpts(HEAD.wall + b)).translate(0, 0, HEAD_BACK_Z + b), materials.headWood);
  back.name = 'headBack';

  // Frame: the outline with the slot cut through it
  const frameShape = roundedRect(-hw + b, y0 + b, hw - b, y1 - b, HEAD.cornerRadius);
  const [lo, hi] = slotRange;
  const slot = symmetricShape((y) => slotHalfWidth(y) + b, lo - b, hi + b, 160);
  frameShape.holes.push(new THREE.Path(slot.slice().reverse()));
  const frameDepth = HEAD.depth - HEAD.wall;
  const frame = new THREE.Mesh(new THREE.ExtrudeGeometry(frameShape, extrudeOpts(frameDepth)).translate(0, 0, HEAD_BACK_Z + HEAD.wall + b), materials.headWood);
  frame.name = 'headFrame';

  // Floor of the slot, a shade darker, so the inside reads as a cavity
  const floor = new THREE.Mesh(new THREE.ShapeGeometry(new THREE.Shape(slot)).translate(0, 0, HEAD_BACK_Z + HEAD.wall + 0.005), materials.cavity);
  floor.name = 'slotFloor';

  [back, frame, floor].forEach((m) => { m.castShadow = m.receiveShadow = true; group.add(m); });
  return group;
}
