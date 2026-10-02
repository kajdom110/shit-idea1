// Standalone preview: the finished instrument in the studio, driven by page scroll through the
// cinematic scenes, with free rotation by drag on top. Renders only while something moves.
import * as THREE from 'three';
import { createScene, pixelAngle } from './scene.js';
import { createMaterials, stringUniforms } from './materials/index.js';
import { buildInstrument } from './index.js';
import { createRotationControls } from './controls.js';
import { sampleScroll } from './scroll.js';
import { PIVOT } from './dimensions.js';

const stage = document.getElementById('stage');
const studio = createScene(stage);
const { renderer, camera, pivot, holder } = studio;

const manager = new THREE.LoadingManager();
let dirty = true;
manager.onProgress = () => { dirty = true; };
manager.onLoad = () => { dirty = true; document.getElementById('loading').classList.add('done'); };

const materials = createMaterials({ anisotropy: renderer.capabilities.getMaxAnisotropy(), manager });
const { root } = buildInstrument(materials);
holder.add(root);

const canvas = renderer.domElement;
canvas.tabIndex = 0;
canvas.setAttribute('aria-label', 'تار سه‌بعدی؛ برای چرخاندن بکشید یا از کلیدهای جهت استفاده کنید');
const controls = createRotationControls(canvas);

studio.onResize((w, h) => {
  stringUniforms.pixelAngle.value = pixelAngle(camera, h);
  dirty = true;
});
studio.resize();

/* ---------- grain overlay ---------- */
(() => {
  const c = document.createElement('canvas');
  c.width = c.height = 160;
  const g = c.getContext('2d'), im = g.createImageData(160, 160);
  for (let i = 0; i < im.data.length; i += 4) {
    const v = Math.random() * 255;
    im.data[i] = im.data[i + 1] = im.data[i + 2] = v;
    im.data[i + 3] = 255;
  }
  g.putImageData(im, 0, 0);
  document.getElementById('grain').style.backgroundImage = 'url(' + c.toDataURL() + ')';
})();

/* ---------- scroll ---------- */
const captions = [...document.querySelectorAll('.caption')];
const dots = [...document.querySelectorAll('.rail span')];
const scrollTarget = () => {
  const max = document.documentElement.scrollHeight - window.innerHeight;
  return max > 0 ? window.scrollY / max : 0;
};
let progress = scrollTarget();
window.addEventListener('scroll', () => { dirty = true; }, { passive: true });

const pivotOffset = new THREE.Vector3(PIVOT.x, PIVOT.y, PIVOT.z);
const targetWorld = new THREE.Vector3();
const sceneQ = new THREE.Quaternion();

function apply(state) {
  sceneQ.copy(state.quaternion);
  pivot.quaternion.copy(controls.quaternion).multiply(sceneQ);
  // the look-at point is a spot on the instrument, so it follows the instrument as it turns
  targetWorld.copy(state.target).sub(pivotOffset).applyQuaternion(pivot.quaternion);
  camera.position.set(targetWorld.x, targetWorld.y + Math.sin(state.elev) * state.dist, targetWorld.z + Math.cos(state.elev) * state.dist);
  camera.lookAt(targetWorld);
  renderer.toneMappingExposure = state.exposure;
  studio.setDepthOfField(camera.position.distanceTo(targetWorld), state.aperture);

  let best = 0, bestW = -1;
  captions.forEach((el, i) => {
    const w = state.captions[i] || 0;
    el.style.opacity = THREE.MathUtils.smoothstep(w, 0.62, 1).toFixed(3);
    el.style.visibility = w > 0.62 ? 'visible' : 'hidden';
    if (w > bestW) { bestW = w; best = i; }
  });
  dots.forEach((d, i) => d.classList.toggle('on', i === best));
}

/* ---------- loop ---------- */
const clock = new THREE.Clock();
function frame() {
  const dt = Math.min(clock.getDelta(), 0.05);
  const goal = scrollTarget();
  const scrolling = Math.abs(goal - progress) > 1e-4;
  // the camera follows the scroll with a short, smooth lag rather than jumping with each wheel step
  progress += (goal - progress) * (1 - Math.exp(-dt * 6));
  if (!scrolling) progress = goal;
  const moving = controls.update(dt, { scrolling });

  if (scrolling || moving || dirty) {
    apply(sampleScroll(progress));
    studio.render();
    dirty = false;
  }
  requestAnimationFrame(frame);
}
frame();
