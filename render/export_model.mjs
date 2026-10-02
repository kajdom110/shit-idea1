// Phase R1: exports the instrument built by tar3d/ (the same geometry as the web preview) to
// one OBJ file, one object per mesh, named "<part>__<mesh>__<material>" so the Blender scene
// script can give every surface its physical material.
//
//   cd render && npm install && node --import ./three-resolver.mjs export_model.mjs   → build/tar.obj
//
// Units stay centimetres; Blender imports them at 0.01 so the scene is in real metres.
import fs from 'fs';
import * as THREE from 'three';
import { buildInstrument } from '../tar3d/index.js';
import { KEYFRAMES } from '../tar3d/scroll.js';
import { PIVOT } from '../tar3d/dimensions.js';

// Plain materials that only carry their key as a name; the real look is built in Blender.
const materials = new Proxy({}, {
  get: (cache, key) => {
    if (typeof key !== 'string') return undefined;
    if (!cache[key]) { cache[key] = new THREE.MeshStandardMaterial(); cache[key].name = key; }
    return cache[key];
  },
});

const { root, parts } = buildInstrument(materials);
root.updateMatrixWorld(true);

const out = [];
let vBase = 1, tBase = 1, nBase = 1;
const v = new THREE.Vector3(), n = new THREE.Vector3(), nm = new THREE.Matrix3();
for (const [part, group] of Object.entries(parts)) {
  group.traverse((obj) => {
    if (!obj.isMesh) return;
    const g = obj.geometry.index ? obj.geometry.toNonIndexed() : obj.geometry;
    const pos = g.attributes.position, nor = g.attributes.normal, uv = g.attributes.uv;
    nm.getNormalMatrix(obj.matrixWorld);
    out.push(`o ${part}__${obj.name || 'mesh'}__${obj.material.name}`);
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i).applyMatrix4(obj.matrixWorld);
      out.push(`v ${v.x.toFixed(5)} ${v.y.toFixed(5)} ${v.z.toFixed(5)}`);
    }
    for (let i = 0; i < pos.count; i++) {
      if (uv) out.push(`vt ${uv.getX(i).toFixed(5)} ${uv.getY(i).toFixed(5)}`);
      else out.push('vt 0 0');
    }
    for (let i = 0; i < pos.count; i++) {
      if (nor) n.fromBufferAttribute(nor, i).applyMatrix3(nm).normalize(); else n.set(0, 0, 1);
      out.push(`vn ${n.x.toFixed(4)} ${n.y.toFixed(4)} ${n.z.toFixed(4)}`);
    }
    out.push(`usemtl ${obj.material.name}`);
    for (let i = 0; i < pos.count; i += 3) {
      const f = (k) => `${vBase + i + k}/${tBase + i + k}/${nBase + i + k}`;
      out.push(`f ${f(0)} ${f(1)} ${f(2)}`);
    }
    vBase += pos.count; tBase += pos.count; nBase += pos.count;
  });
}
fs.mkdirSync('build', { recursive: true });
fs.writeFileSync('build/tar.obj', out.join('\n'));
// The scroll scenes and the pivot, so the render follows exactly the same camera path as the web page.
fs.writeFileSync('build/scenes.json', JSON.stringify({ pivot: PIVOT, keyframes: KEYFRAMES }, null, 2));
console.log('wrote build/tar.obj and build/scenes.json', Object.keys(parts).length, 'parts', (vBase - 1), 'vertices');
