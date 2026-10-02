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
