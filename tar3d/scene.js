// Renderer, camera and lights. Phase 1 uses a temporary neutral light rig;
// phase 6 replaces it with the final studio lighting.
import * as THREE from 'three';
import { PIVOT } from './dimensions.js';

export function createScene(container) {
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0d0c0b);

  const camera = new THREE.PerspectiveCamera(24, 1, 1, 2000);
  camera.position.set(0, 0, 260);

  // Temporary lighting: enough to read the shapes.
  scene.add(new THREE.HemisphereLight(0xffffff, 0x222222, 1.2));
  const key = new THREE.DirectionalLight(0xffffff, 1.6);
  key.position.set(-80, 120, 160);
  scene.add(key);

  // The instrument hangs from a pivot group so it turns about its visual centre.
  const pivot = new THREE.Group();
  scene.add(pivot);
  const holder = new THREE.Group();
  holder.position.set(-PIVOT.x, -PIVOT.y, -PIVOT.z);
  pivot.add(holder);

  function resize() {
    const w = container.clientWidth, h = container.clientHeight;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize);
  resize();

  return { renderer, scene, camera, pivot, holder, resize };
}
