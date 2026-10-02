// Heel (pashneh): the pointed tongue that carries the back of the neck down onto the
// naghareh. It is built as a raised skin over the bowl: at every point it stands a little
// off the back surface, thinning towards its edges so it melts into the bowl without a seam,
// and ends in a thick rounded nose (R3).
import * as THREE from 'three';
import { BODY, NECK, HEEL } from '../dimensions.js';
import { lerp, clamp, loft } from './util.js';
import { backZ } from './body.js';

export function buildHeel(materials) {
  const yTop = BODY.topY - 0.2; // starts inside the neck
  const yTip = NECK.bottomY - HEEL.length;
  const noseStart = yTip + HEEL.noseLength;
  const rows = [];
  const nRows = 70, nAcross = 28;

  for (let j = 0; j <= nRows; j++) {
    const y = lerp(yTop, yTip, j / nRows);
    const s = clamp((yTop - y) / (yTop - yTip), 0, 1);
    // Rounded nose: width and thickness close like a quarter circle over the last stretch.
    const nose = y < noseStart ? Math.sqrt(Math.max(0, 1 - Math.pow((noseStart - y) / HEEL.noseLength, 2))) : 1;
    const hw = Math.max(lerp(NECK.widthAtBody / 2, HEEL.tipWidth / 2, Math.pow(s, 0.8)) * nose, 1e-3);
    const thick = lerp(HEEL.thicknessTop, HEEL.thicknessTip, s) * nose;

    const pts = [];
    for (let i = 0; i <= nAcross; i++) {
      const x = lerp(hw, -hw, i / nAcross);
      const p = Math.sqrt(Math.max(0, 1 - (x / hw) * (x / hw)));
      // Edges sit a hair inside the bowl so no gap or flicker shows where they meet.
      pts.push([x, backZ(x, y) - (thick * Math.pow(p, 0.7) - 0.03)]);
    }
    rows.push({ y, pts });
  }

  const mesh = new THREE.Mesh(loft(rows), materials.wood);
  mesh.name = 'heel';
  mesh.castShadow = mesh.receiveShadow = true;
  const group = new THREE.Group();
  group.name = 'heel';
  group.add(mesh);
  return group;
}
