// Heel (pashneh): the back of the neck thickens above the body, then runs down the back
// of the naghareh as a pointed tongue with a thick rounded nose (R3, R6).
//
// Each row is the outer envelope of two surfaces:
//   – the neck back, deepened by a bulge that grows towards the body;
//   – a ridge standing off the bowl, thinning to nothing at its edges.
// Taking the outermost of the two gives one continuous surface where the neck meets the
// bowl, with no gap and no seam.
import * as THREE from 'three';
import { BODY, NECK, HEEL } from '../dimensions.js';
import { lerp, clamp, smoothstep, loft, dSectionZ } from './util.js';
import { W, backZ } from './body.js';
import { neckHalfWidth, neckDepth, NECK_TOP_Z } from './neck.js';

const yTip = NECK.bottomY - HEEL.length;

function smin(a, b, k) {
  const h = Math.max(k - Math.abs(a - b), 0) / k;
  return Math.min(a, b) - h * h * k * 0.25;
}
const noseStart = yTip + HEEL.noseLength;

// Extra depth of the neck back, from nothing at HEEL.startY to neckBulge at the body.
export const heelBulge = (y) => HEEL.neckBulge * smoothstep(HEEL.startY, BODY.topY, y);

function ridgeThickness(y) {
  const s = clamp((BODY.topY - y) / (BODY.topY - yTip), 0, 1);
  const t = s < 0.5 ? lerp(HEEL.thicknessTop, HEEL.thicknessMid, s / 0.5) : lerp(HEEL.thicknessMid, HEEL.thicknessTip, (s - 0.5) / 0.5);
  return t;
}

// Half-width and nose factor of the tongue below the top of the body.
function tongue(y) {
  const s = clamp((BODY.topY - y) / (BODY.topY - yTip), 0, 1);
  const nose = y < noseStart ? Math.sqrt(Math.max(0, 1 - Math.pow((noseStart - y) / HEEL.noseLength, 2))) : 1;
  const hw = lerp(NECK.widthAtBody / 2, HEEL.tipWidth / 2, Math.pow(s, 0.8)) * nose;
  return { hw: Math.max(hw, 1e-3), nose };
}

// Outer surface z at (x, y), or null where neither surface exists.
export function heelZ(x, y) {
  let z = null;
  const nhw = neckHalfWidth(y);
  if (y >= NECK.boardEndY && Math.abs(x) <= nhw) {
    // Starts just inside the neck and comes out through it as the bulge grows.
    z = dSectionZ(x, nhw, NECK_TOP_Z, neckDepth(y) + heelBulge(y) - 0.02, NECK.sectionExponent);
  }
  if (y < BODY.topY && Math.abs(x) < W(y)) {
    const { hw, nose } = tongue(y);
    if (Math.abs(x) <= hw) {
      const p = Math.sqrt(Math.max(0, 1 - (x / hw) * (x / hw)));
      const zr = backZ(x, y) - (ridgeThickness(y) * nose * Math.pow(p, 0.7) - 0.03);
      // Soft minimum: fills the inside corner where the neck back meets the bowl with a fillet.
      z = z === null ? zr : smin(z, zr, 1.5);
    }
  }
  return z;
}

export function buildHeel(materials) {
  const rows = [];
  const nRows = 110, nAcross = 30;
  const yTop = HEEL.startY;
  for (let j = 0; j <= nRows; j++) {
    const y = lerp(yTop, yTip, j / nRows);
    // Slightly narrower than the neck above the body, so its edges stay inside the neck's rounded corners.
    const hw = y >= BODY.topY ? neckHalfWidth(y) * 0.97 : tongue(y).hw;
    const pts = [];
    for (let i = 0; i <= nAcross; i++) {
      const x = lerp(hw, -hw, i / nAcross);
      let z = heelZ(x, y);
      if (z === null) z = y < BODY.topY ? backZ(x, y) + 0.03 : NECK_TOP_Z;
      pts.push([x, z]);
    }
    rows.push({ y, pts });
  }
  const mesh = new THREE.Mesh(loft(rows), materials.lightWood);
  mesh.name = 'heel';
  mesh.castShadow = mesh.receiveShadow = true;
  const group = new THREE.Group();
  group.name = 'heel';
  group.add(mesh);
  return group;
}

// Back of the neck-and-heel at (x, y) for fret wraps; falls back to the plain neck.
export function wrapBackZ(x, y) {
  const z = heelZ(x, y);
  return z === null ? dSectionZ(x, neckHalfWidth(y), NECK_TOP_Z, neckDepth(y), NECK.sectionExponent) : z;
}
