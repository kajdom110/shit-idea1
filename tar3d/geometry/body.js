// Body: kaseh (lower bowl) and naghareh (upper bowl) as one carved shell, the diagonal
// valley on the back, the wooden top with its rounded outer edge, the khatam band and
// the two heart-shaped skin openings.
//
// Everything is driven by three profiles along the length (y):
//   W(y) – half-width of the outline seen from the front
//   D(y) – depth of the back below the skin plane
//   O(y) – half-width of the skin openings (the two hearts as one region)
import * as THREE from 'three';
import { BODY } from '../dimensions.js';
import { clamp, smax, lobe, lobeReach, stations, loft, symmetricShape, shapeWithHoles, wallStrip } from './util.js';

const P_OUTLINE = 2.1; // slightly fuller than an ellipse, as in the photos
const P_DEPTH = 2.0;

/* ---------- outline W(y) ---------- */
const K = BODY.kaseh, N = BODY.naghareh;
const kCentre = K.widestAt * BODY.waistY;
const nCentre = BODY.waistY + N.widestAt * (BODY.length - BODY.waistY);
const kHalf = K.width / 2, nHalf = N.width / 2;
// Both lobes pass through the same half-width at the waist; the blend then adds k/4,
// which lands the waist exactly on BODY.waistWidth.
const waistHalf = BODY.waistWidth / 2 - BODY.waistBlend / 4;
const kAbove = lobeReach(BODY.waistY - kCentre, waistHalf, kHalf, P_OUTLINE);
const nBelow = lobeReach(nCentre - BODY.waistY, waistHalf, nHalf, P_OUTLINE);

export function W(y) {
  const a = lobe(y, kCentre, kCentre, kAbove, kHalf, P_OUTLINE);
  const b = lobe(y, nCentre, nBelow, BODY.topY - nCentre, nHalf, P_OUTLINE);
  return smax(a, b, BODY.waistBlend);
}

/* ---------- depth D(y) ---------- */
const kDeep = K.deepestAt * BODY.waistY;
const waistDepth = 0.62 * K.depth; // R6: the back narrows at the waist, then the valley cuts in
const dBlend = 2.4;
const kDAbove = lobeReach(BODY.waistY - kDeep, waistDepth - dBlend / 4, K.depth, P_DEPTH);
const nDBelow = lobeReach(nCentre - BODY.waistY, waistDepth - dBlend / 4, N.depth, P_DEPTH);

export function D(y) {
  const a = lobe(y, kDeep, kDeep, kDAbove, K.depth, P_DEPTH);
  const b = lobe(y, nCentre, nDBelow, BODY.topY - nCentre, N.depth, P_DEPTH);
  return smax(a, b, dBlend);
}

/* ---------- cross-section ---------- */
const TOP_Z = BODY.rim.lipHeight;
const E = 2 / BODY.sectionExponent;
export const topZ = TOP_Z;
// Radius of the rounded outer edge, shrinking where the body narrows to a point.
export const rEff = (y) => Math.min(BODY.rim.filletRadius, 0.4 * W(y));

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
  const w = W(y), dep = D(y), zt = TOP_Z - rEff(y);
  if (w <= 1e-4 || Math.abs(x) >= w) return zt;
  const c = Math.pow(Math.abs(x) / w, 1 / E);
  const s = Math.sqrt(Math.max(0, 1 - c * c));
  const f = Math.pow(s, E);
  return zt - (zt + dep) * f + valleyLift(x, y, clamp((f - 0.15) / 0.45, 0, 1));
}

function section(y, nFillet, nBack) {
  const w = W(y), dep = D(y), r = rEff(y), zt = TOP_Z - r;
  const pts = [];
  // right rounded edge: from the top face down to the wall
  for (let i = 0; i <= nFillet; i++) {
    const a = (Math.PI / 2) * (1 - i / nFillet);
    pts.push([w - r + r * Math.cos(a), zt + r * Math.sin(a)]);
  }
  // wall and back, right to left
  for (let i = 1; i <= nBack; i++) {
    const th = (Math.PI * i) / (nBack + 1);
    const c = Math.cos(th), s = Math.sin(th);
    const x = w * Math.sign(c) * Math.pow(Math.abs(c), E);
    const f = Math.pow(Math.abs(s), E);
    const z = zt - (zt + dep) * f + valleyLift(x, y, clamp((f - 0.15) / 0.45, 0, 1));
    pts.push([x, z]);
  }
  // left rounded edge: from the wall up to the top face
  for (let i = 0; i <= nFillet; i++) {
    const a = Math.PI / 2 + (Math.PI / 2) * (1 - i / nFillet);
    pts.push([-(w - r) + r * Math.cos(a), zt + r * Math.sin(a)]);
  }
  return pts;
}

/* ---------- skin openings O(y) ---------- */
const S = BODY.skin;
const lowerTip = BODY.waistY + S.tipOverlap;
const upperTip = BODY.waistY - S.tipOverlap;
const lowerHalf = kHalf - S.border, upperHalf = nHalf - S.border;
const taper = (t) => Math.pow(Math.max(0, 1 - t * t), 1.15) * (1 - 0.3 * t);

function lowerHeart(y) {
  if (y < S.bottomGap || y > lowerTip) return 0;
  if (y <= kCentre) return lobe(y, kCentre, kCentre - S.bottomGap, 1, lowerHalf, P_OUTLINE);
  const t = (y - kCentre) / (lowerTip - kCentre);
  return lowerHalf * taper(t) + S.tipWidth * t;
}
function upperHeart(y) {
  if (y < upperTip || y > S.topY) return 0;
  if (y >= nCentre) return lobe(y, nCentre, 1, S.topY - nCentre, upperHalf, P_OUTLINE);
  const t = (nCentre - y) / (nCentre - upperTip);
  return upperHalf * taper(t) + S.tipWidth * t;
}
export const O = (y) => Math.max(lowerHeart(y), upperHeart(y));
export const SKIN_RANGE = [S.bottomGap, S.topY];

// Exact outward offset of the region |x| ≤ O(y) by radius r (Minkowski sum with a disc).
function offsetHalfWidth(fn, r, y) {
  let best = 0;
  for (let k = -12; k <= 12; k++) {
    const s = (k / 12) * r;
    const v = fn(y + s);
    if (v > 0) best = Math.max(best, v + Math.sqrt(r * r - s * s));
  }
  return best;
}
const inlayOuter = (y) => offsetHalfWidth(O, BODY.rim.inlayWidth, y);

/* ---------- build ---------- */
export function buildBody(materials, quality) {
  const group = new THREE.Group();
  group.name = 'body';

  // Shell
  const nFillet = 8;
  const nBack = quality.bodyRadial - 2 * (nFillet + 1);
  const ys = stations(0, BODY.topY, quality.bodyStations);
  const rows = ys.map((y) => ({ y, pts: section(y, nFillet, nBack) }));
  const shell = new THREE.Mesh(loft(rows, { vScale: 2.4 }), materials.wood);
  shell.name = 'shell';
  shell.castShadow = shell.receiveShadow = true;
  group.add(shell);

  // Wooden top: inside the rounded edge, with one hole for the khatam band and skin
  const n = Math.round(quality.bodyStations * 1.4);
  const outer = symmetricShape((y) => W(y) - rEff(y), 0, BODY.topY, n);
  const [s0, s1] = SKIN_RANGE, iw = BODY.rim.inlayWidth;
  const inlayPts = symmetricShape(inlayOuter, s0 - iw, s1 + iw, n);
  const skinPts = symmetricShape(O, s0, s1, n);

  // Geometry is moved, not the mesh, so the solid wood pattern lines up across all parts.
  const top = new THREE.Mesh(new THREE.ShapeGeometry(shapeWithHoles(outer, [inlayPts]), 1).translate(0, 0, TOP_Z), materials.wood);
  top.name = 'top';
  top.receiveShadow = true;
  group.add(top);

  const inlay = new THREE.Mesh(new THREE.ShapeGeometry(shapeWithHoles(inlayPts, [skinPts]), 1).translate(0, 0, TOP_Z), materials.inlay);
  inlay.name = 'inlay';
  group.add(inlay);

  // Step down from the top to the skin, all around the openings
  const step = new THREE.Mesh(wallStrip(skinPts, 0, TOP_Z, true), materials.wood);
  step.name = 'step';
  group.add(step);

  const skin = new THREE.Mesh(new THREE.ShapeGeometry(shapeWithHoles(skinPts), 1), materials.skin);
  skin.name = 'skin';
  skin.receiveShadow = true;

  return { body: group, skin };
}

// Exposed for later phases (neck seat, tailpiece seat, bridge placement).
export const bodyProfile = { W, D, O, backZ, rEff, topZ: TOP_Z, kCentre, nCentre };
