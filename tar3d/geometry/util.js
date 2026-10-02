// Shared geometry helpers.
import * as THREE from 'three';

export const lerp = (a, b, t) => a + (b - a) * t;
export const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
export const smoothstep = (a, b, v) => {
  const t = clamp((v - a) / (b - a), 0, 1);
  return t * t * (3 - 2 * t);
};

// Polynomial smooth maximum: equals max(a, b) away from the crossing and rounds the
// corner within a band of width k. Fades out when both values approach zero, so lobes
// still close to a point at the ends.
export function smax(a, b, k) {
  const h = Math.max(k - Math.abs(a - b), 0) / k;
  return Math.max(a, b) + h * h * k * 0.25 * Math.min(1, (a + b) / k);
}

// A lobe: half-width of a superellipse arc along y, with separate reach below and above
// its centre. Returns 0 outside.
export function lobe(y, centre, below, above, halfWidth, p) {
  const b = y < centre ? below : above;
  const t = Math.abs(y - centre) / b;
  if (t >= 1) return 0;
  return halfWidth * Math.pow(1 - Math.pow(t, p), 1 / p);
}

// Reach of a lobe so that it passes through half-width h at distance d from its centre.
export function lobeReach(d, h, halfWidth, p) {
  return Math.abs(d) / Math.pow(1 - Math.pow(h / halfWidth, p), 1 / p);
}

// Stations along [a, b], denser towards both ends where curvature is highest.
export function stations(a, b, n) {
  const out = [];
  for (let i = 0; i <= n; i++) out.push(lerp(a, b, (1 - Math.cos((Math.PI * i) / n)) / 2));
  return out;
}

// Loft: rows of cross-section points (same count per row) into an indexed mesh.
// rows: [{ y, pts: [[x, z], ...] }]. UVs: u across the section, v along y.
export function loft(rows, { vScale = 1, closed = false } = {}) {
  const nx = rows[0].pts.length;
  const pos = [], uv = [], idx = [];
  const y0 = rows[0].y, y1 = rows[rows.length - 1].y;
  rows.forEach((r) => r.pts.forEach((p, i) => {
    pos.push(p[0], p.length > 2 ? p[2] : r.y, p[1]);
    uv.push(i / (nx - 1), ((r.y - y0) / (y1 - y0)) * vScale);
  }));
  const cols = closed ? nx : nx - 1;
  for (let j = 0; j < rows.length - 1; j++) for (let i = 0; i < cols; i++) {
    const i2 = (i + 1) % nx;
    const a = j * nx + i, b = j * nx + i2, c = a + nx, d = b + nx;
    idx.push(a, b, c, b, d, c);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

// A symmetric flat shape from a half-width function over [y0, y1], with optional holes
// (each also a half-width function and range). Lies in the plane z = 0.
export function symmetricShape(halfWidth, y0, y1, n) {
  const right = [], left = [];
  for (let i = 0; i <= n; i++) {
    const y = lerp(y0, y1, i / n);
    const w = Math.max(halfWidth(y), 0.0005);
    right.push(new THREE.Vector2(w, y));
    left.push(new THREE.Vector2(-w, y));
  }
  return right.concat(left.reverse());
}

export function shapeWithHoles(outer, holes = []) {
  const s = new THREE.Shape(outer);
  holes.forEach((h) => s.holes.push(new THREE.Path(h)));
  return s;
}

// Vertical strip joining a closed outline at z0 to the same outline at z1. With a
// counter-clockwise outline, `inward` turns the faces towards the inside (a hole's wall).
export function wallStrip(points, z0, z1, inward = false) {
  const pos = [], idx = [];
  points.forEach((p) => { pos.push(p.x, p.y, z0, p.x, p.y, z1); });
  const n = points.length;
  for (let i = 0; i < n; i++) {
    const j = (i + 1) % n, a = i * 2, b = a + 1, c = j * 2, d = c + 1;
    if (inward) idx.push(a, b, c, b, d, c);
    else idx.push(a, c, b, b, c, d);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

// Rounded "D" cross-section: flat top at zTop between ±hw with rounded corners of radius r,
// and a superellipse back reaching zTop − depth. Points run from the right top edge, down
// and round the back, to the left top edge, as [x, z]. With `closeTop`, the flat top is
// added back to the start so the loop is closed.
export function dSection(hw, zTop, depth, r, nFillet, nBack, exponent, closeTop = false) {
  const e = 2 / exponent, zt = zTop - r, zb = zTop - depth;
  const pts = [];
  for (let i = 0; i <= nFillet; i++) {
    const a = (Math.PI / 2) * (1 - i / nFillet);
    pts.push([hw - r + r * Math.cos(a), zt + r * Math.sin(a)]);
  }
  for (let i = 1; i <= nBack; i++) {
    const th = (Math.PI * i) / (nBack + 1);
    const c = Math.cos(th), s = Math.sin(th);
    pts.push([hw * Math.sign(c) * Math.pow(Math.abs(c), e), zt - (zt - zb) * Math.pow(Math.abs(s), e)]);
  }
  for (let i = 0; i <= nFillet; i++) {
    const a = Math.PI / 2 + (Math.PI / 2) * (1 - i / nFillet);
    pts.push([-(hw - r) + r * Math.cos(a), zt + r * Math.sin(a)]);
  }
  if (closeTop) {
    const n = 6;
    for (let i = 1; i < n; i++) pts.push([lerp(-(hw - r), hw - r, i / n), zTop]);
  }
  return pts;
}

// z of the back of a dSection at x (ignoring the small top corners).
export function dSectionZ(x, hw, zTop, depth, exponent) {
  const t = Math.min(1, Math.abs(x) / hw);
  return zTop - depth * Math.pow(Math.max(0, 1 - Math.pow(t, exponent)), 1 / exponent);
}

// Small deterministic random generator, so hand-made irregularities look the same on every load.
export function seeded(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}
