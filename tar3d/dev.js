// Development viewer: free rotation in every direction, a centimetre grid, part toggles,
// wireframe and per-part bounding boxes with their measured sizes.
import * as THREE from 'three';
import { TrackballControls } from 'three/addons/controls/TrackballControls.js';
import { createScene } from './scene.js';
import { createMaterials } from './materials/index.js';
import { buildInstrument } from './index.js';

const { renderer, scene, camera, holder } = createScene(document.getElementById('stage'));
const materials = createMaterials({ anisotropy: renderer.capabilities.getMaxAnisotropy() });
const { root, parts } = buildInstrument(materials);
holder.add(root);

const controls = new TrackballControls(camera, renderer.domElement);
controls.rotateSpeed = 3;
controls.zoomSpeed = 1.2;
controls.noPan = false;
controls.dynamicDampingFactor = 0.15;

// Helpers
const grid = new THREE.GridHelper(200, 20, 0x5a5048, 0x2e2925);
grid.position.y = -60;
scene.add(grid);
const axes = new THREE.AxesHelper(30);
axes.visible = false;
holder.add(axes);
const boxHelpers = Object.values(parts).map((p) => {
  const h = new THREE.BoxHelper(p, 0xd39a62);
  h.visible = false;
  scene.add(h);
  return h;
});

const DIST = 230;
const VIEWS = {
  front: [0, 0, DIST], side: [DIST, 0, 0], back: [0, 0, -DIST],
  top: [0, DIST, 0.01], bottom: [0, -DIST, 0.01],
};
document.querySelectorAll('[data-view]').forEach((b) => b.addEventListener('click', () => {
  camera.position.set(...VIEWS[b.dataset.view]);
  camera.up.set(0, 1, 0);
  controls.target.set(0, 0, 0);
  camera.lookAt(0, 0, 0);
}));

document.getElementById('wire').addEventListener('change', (e) => {
  Object.values(materials).forEach((m) => { m.wireframe = e.target.checked; });
});
document.getElementById('grid').addEventListener('change', (e) => { grid.visible = e.target.checked; });
document.getElementById('axes').addEventListener('change', (e) => { axes.visible = e.target.checked; });
document.getElementById('boxes').addEventListener('change', (e) => { boxHelpers.forEach((h) => { h.visible = e.target.checked; }); });

const NAMES = { body: 'بدنه', skin: 'پوست', neck: 'دسته', heel: 'پاشنه', frets: 'پرده‌ها', head: 'سرپنجه', pegs: 'گوشی‌ها', hardware: 'خرک و سیم‌گیر', strings: 'سیم‌ها' };
const list = document.getElementById('partList');
const sizes = document.getElementById('sizes');
Object.entries(parts).forEach(([key, obj]) => {
  const label = document.createElement('label');
  label.innerHTML = '<input type="checkbox" checked id="part-' + key + '"> ' + (NAMES[key] || key);
  label.querySelector('input').addEventListener('change', (e) => { obj.visible = e.target.checked; });
  list.appendChild(label);

  const size = new THREE.Box3().setFromObject(obj).getSize(new THREE.Vector3());
  const row = document.createElement('tr');
  row.innerHTML = '<td>' + key + '</td><td>' + [size.x, size.y, size.z].map((v) => v.toFixed(1)).join(' × ') + '</td>';
  sizes.appendChild(row);
});

function frame() {
  controls.update();
  boxHelpers.forEach((h) => h.visible && h.update());
  renderer.render(scene, camera);
  requestAnimationFrame(frame);
}
window.addEventListener('resize', () => controls.handleResize());
frame();
