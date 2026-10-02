// Body: kaseh (lower bowl) and naghareh (upper bowl) as one carved shell, the diagonal
// valley on the back, the varnished wooden top with its rounded outer edge, the pale
// wooden lip that rolls down into the skin, and the two heart-shaped skin openings.
//
// Everything is driven by four profiles along the length (y), measured from the reference
// photos (tools/measure_body.py → bodyData.js):
//   W(y) – half-width of the outline seen from the front      (R4) — the widest part of the
//          bowl, which bulges out behind the flat face as on the photos
//   F(y) – half-width of the flat face itself (lip plus a narrow band of varnished wood)
//   D(y) – depth of the back below the skin plane              (R6)
//   L(y) – half-width of the outer edge of the pale lip        (R4, traced)
//   O(y) – half-width of the skin openings (both hearts)       (R4, traced)
import * as THREE from 'three';
import { BODY } from '../dimensions.js';
import { OUTLINE, DEPTH, SKIN, LIP } from '../bodyData.js';
import { clamp, stations, loft, symmetricShape, shapeWithHoles } from './util.js';

/* ---------- profiles ---------- */
// Light smoothing of silhouette samples (5 px steps), then Catmull–Rom interpolation so the
// lofted surface has no ridges between samples.
function smoothed(pts, k = 1) {
  return pts.map(([y], i) => {
    let s = 0, n = 0;
    for (let j = Math.max(0, i - k); j <= Math.min(pts.length - 1, i + k); j++) { s += pts[j][1]; n++; }
    return [y, s / n];
  });
}
function catmull(pts) {
  return (y) => {
    if (y <= pts[0][0]) return pts[0][1];
    if (y >= pts[pts.length - 1][0]) return pts[pts.length - 1][1];
    let i = 0;
    while (pts[i + 1][0] < y) i++;
    const p0 = pts[Math.max(0, i - 1)][1], p1 = pts[i][1], p2 = pts[i + 1][1], p3 = pts[Math.min(pts.length - 1, i + 2)][1];
    const t = (y - pts[i][0]) / (pts[i + 1][0] - pts[i][0]);
    return 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t);
  };
}
function linear(pts) {
  return (y) => {
    if (y < pts[0][0] || y > pts[pts.length - 1][0]) return 0;
    let i = 0;
    while (i < pts.length - 2 && pts[i + 1][0] < y) i++;
    const t = (y - pts[i][0]) / (pts[i + 1][0] - pts[i][0] || 1);
    return pts[i][1] + (pts[i + 1][1] - pts[i][1]) * clamp(t, 0, 1);
  };
}
// Close a measured profile to zero at both ends with a quarter-round cap, so the body is
// rounded at the bottom of the kaseh and at the shoulders of the naghareh.
function capped(pts, top) {
  const f = catmull(smoothed(pts)), y0 = pts[0][0], y1 = pts[pts.length - 1][0];
  return (y) => {
    if (y <= 0 || y >= top) return 0;
    if (y < y0) return f(y0) * Math.sqrt(1 - Math.pow(1 - y / y0, 2));
    if (y > y1) return f(y1) * Math.sqrt(Math.max(0, 1 - Math.pow((y - y1) / (top - y1), 2)));
    return Math.max(0, f(y));
  };
}

export const W = capped(OUTLINE, BODY.topY);
export const D = capped(DEPTH, BODY.topY);
export const O = linear(SKIN);
export const L = linear(LIP);
export const SKIN_RANGE = [SKIN[0][0], SKIN[SKIN.length - 1][0]];
export const LIP_RANGE = [LIP[0][0], LIP[LIP.length - 1][0]];

/* ---------- cross-section ---------- */
const TOP_Z = BODY.rim.lipHeight;
const E = 2 / BODY.sectionExponent;
export const topZ = TOP_Z;
const B = BODY.bulge;
// Half-width of the flat face: the lip plus a band of varnished wood, never wider than the bowl.
export const F = (y) => {
  const w = W(y);
  return Math.max(0, Math.min(w - B.minOverhang, Math.max(L(y) + B.faceMargin, w * B.minFaceRatio)));
};
// Depth below the face at which the bowl is widest.
const widestZ = (y) => -B.widestAt * D(y);

const V = BODY.valley;
const vTan = Math.tan((V.angleDeg * Math.PI) / 180);
// Diagonal groove: lifts the back towards the skin along a slanted line across the waist.
function valleyLift(x, y, backness) {
  const yv = BODY.waistY + vTan * x;
  const d = (y - yv) / (V.width / 2);
  return V.depth * Math.exp(-d * d) * backness;
}

// z of the back surface at (x, y), used by the heel and anything else that sits on it.
export function backZ(x, y) {
  const w = W(y), dep = D(y), zw = widestZ(y);
  if (w <= 1e-4 || Math.abs(x) >= w) return zw;
  const c = Math.pow(Math.abs(x) / w, 1 / E);
  const s = Math.sqrt(Math.max(0, 1 - c * c));
  const f = Math.pow(s, E);
  return zw - (dep + zw) * f + valleyLift(x, y, clamp((f - 0.15) / 0.45, 0, 1));
}

// One cross-section, right face edge → round the back → left face edge:
//   shoulder – a quarter ellipse from the face edge out to the widest point (tangent to the face,
//              so the edge is naturally rounded), then
//   back     – a superellipse from the widest point round to the deepest point and back up.
function section(y, nShoulder, nBack) {
  const w = W(y), f = F(y), dep = D(y), zw = widestZ(y);
  const pts = [];
  const shoulder = (side) => {
    const out = [];
    for (let i = 0; i <= nShoulder; i++) {
      const a = (Math.PI / 2) * (i / nShoulder); // 0 at the face edge, π/2 at the widest point
      out.push([side * (f + (w - f) * Math.sin(a)), zw + (TOP_Z - zw) * Math.cos(a)]);
    }
    return out;
  };
  pts.push(...shoulder(1));
  for (let i = 1; i <= nBack; i++) {
    const th = (Math.PI * i) / (nBack + 1);
    const c = Math.cos(th), s = Math.sin(th);
    const x = w * Math.sign(c) * Math.pow(Math.abs(c), E);
    const g = Math.pow(Math.abs(s), E);
    pts.push([x, zw - (dep + zw) * g + valleyLift(x, y, clamp((g - 0.15) / 0.45, 0, 1))]);
  }
  pts.push(...shoulder(-1).reverse());
  return pts;
}

/* ---------- build ---------- */
export function buildBody(materials, quality) {
  const group = new THREE.Group();
  group.name = 'body';

  // Shell
  const nShoulder = 14;
  const nBack = quality.bodyRadial - 2 * (nShoulder + 1);
  const ys = stations(0, BODY.topY, quality.bodyStations);
  const rows = ys.map((y) => ({ y, pts: section(y, nShoulder, nBack) }));
  const shell = new THREE.Mesh(loft(rows, { vScale: 2.4 }), materials.wood);
  shell.name = 'shell';
  shell.castShadow = shell.receiveShadow = true;
  group.add(shell);

  // Varnished face, from its edge (where the bowl starts to swell) in to the pale lip.
  // Geometry is moved, not the mesh, so the solid wood pattern lines up across all parts.
  const n = 420;
  const outer = symmetricShape(F, 0, BODY.topY, n);
  const lipPts = symmetricShape(L, LIP_RANGE[0], LIP_RANGE[1], n);
  const skinPts = symmetricShape(O, SKIN_RANGE[0], SKIN_RANGE[1], n);
  const top = new THREE.Mesh(new THREE.ShapeGeometry(shapeWithHoles(outer, [lipPts]), 1).translate(0, 0, TOP_Z), materials.wood);
  top.name = 'top';
  top.receiveShadow = true;
  group.add(top);

  // Pale lip (R4): rolls down from the top to the skin with a rounded, convex edge.
  const steps = 5;
  const lipRows = [];
  for (let k = 0; k <= steps; k++) {
    const t = k / steps;
    const z = TOP_Z * Math.cos((t * Math.PI) / 2);
    lipRows.push({
      y: k,
      pts: lipPts.map((p, i) => {
        const q = skinPts[i];
        return [p.x + (q.x - p.x) * t, z, p.y + (q.y - p.y) * t];
      }),
    });
  }
  const lip = new THREE.Mesh(loft(lipRows, { closed: true }), materials.lip || materials.inlay);
  lip.name = 'lip';
  lip.receiveShadow = true;
  group.add(lip);

  const skin = new THREE.Mesh(new THREE.ShapeGeometry(shapeWithHoles(skinPts), 1), materials.skin);
  skin.name = 'skin';
  skin.receiveShadow = true;

  return { body: group, skin };
}

export const bodyProfile = { W, D, F, O, L, backZ, topZ: TOP_Z };
