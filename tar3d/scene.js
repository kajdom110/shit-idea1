// Studio: renderer, camera, lights, reflections and the post-processing chain.
// Lighting follows the soft interior light of reference photo R7 (spec section 12).
//
// The lights stay fixed and the instrument turns beneath them, like a tar on a turntable in a
// photo studio, so every change of light while it turns is a real one.
import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { BokehPass } from 'three/addons/postprocessing/BokehPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';
import { PIVOT } from './dimensions.js';

// The light of a warm interior room (as in reference photo R7), rendered once into a
// reflection and ambient map: beige walls all round, a broad soft light overhead and in front,
// and a warm bounce from the wooden table below. Materials take both their soft fill light and
// their reflections from it, so shadows stay gentle and the varnish shows broad, soft highlights.
function roomEnvironment(renderer) {
  const env = new THREE.Scene();
  const wall = (color, intensity) => new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(intensity), side: THREE.BackSide });
  const room = new THREE.Mesh(new THREE.BoxGeometry(14, 9, 14), [
    wall(0xe8dccb, 0.8), wall(0xe8dccb, 0.8), // side walls
    wall(0xf3ebe0, 0.7), // ceiling
    wall(0x9a5a2c, 0.65), // floor: warm wooden table
    wall(0xeee3d4, 0.95), // wall behind the camera
    wall(0xe2d6c4, 0.7), // wall behind the instrument
  ]);
  env.add(room);
  const panel = (w, h, color, intensity, pos) => {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(intensity), side: THREE.DoubleSide }));
    m.position.set(...pos);
    m.lookAt(0, 0, 0);
    env.add(m);
  };
  panel(7, 5, 0xfff1e0, 3.0, [0, 4.4, 3]); // broad ceiling light, slightly in front
  panel(6, 3.5, 0xfff4e8, 1.7, [0, 1.2, 6.9]); // soft light from the camera side
  const pmrem = new THREE.PMREMGenerator(renderer);
  const tex = pmrem.fromScene(env, 0.04).texture;
  pmrem.dispose();
  return tex;
}

// Background: a warm, dark sweep, a little lighter behind the instrument.
function backdrop() {
  const c = document.createElement('canvas');
  c.width = 16; c.height = 512;
  const g = c.getContext('2d');
  const grad = g.createLinearGradient(0, 0, 0, 512);
  grad.addColorStop(0, '#070707');
  grad.addColorStop(0.45, '#14110f');
  grad.addColorStop(0.75, '#100e0c');
  grad.addColorStop(1, '#060606');
  g.fillStyle = grad;
  g.fillRect(0, 0, 16, 512);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

export function createScene(container, { dof = true } = {}) {
  // Antialiasing comes from the multisampled render target below.
  const renderer = new THREE.WebGLRenderer({ antialias: false, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.shadowMap.enabled = true;
  // variance shadows can be blurred: soft-edged shadows, as under a broad room light
  renderer.shadowMap.type = THREE.VSMShadowMap;
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = backdrop();
  scene.environment = roomEnvironment(renderer);

  // A long lens, as product photographers use: little perspective distortion.
  const camera = new THREE.PerspectiveCamera(24, 1, 5, 2000);
  camera.position.set(0, 0, 270);

  /* ---------- lights ---------- */
  // a gentle directional light only for shape and soft shadows; the room does most of the lighting
  const key = new THREE.DirectionalLight(0xfff3e4, 1.1);
  key.position.set(-60, 160, 140);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  Object.assign(key.shadow.camera, { left: -60, right: 60, top: 60, bottom: -60, near: 10, far: 500 });
  key.shadow.bias = -0.0004;
  key.shadow.normalBias = 0.04;
  key.shadow.radius = 12;
  key.shadow.blurSamples = 16;
  scene.add(key);
  const rimLeft = new THREE.DirectionalLight(0xffe6cc, 0.5);
  rimLeft.position.set(-160, 60, -120);
  const rimRight = new THREE.DirectionalLight(0xffdcbc, 0.4);
  rimRight.position.set(170, 30, -110);
  const fill = new THREE.HemisphereLight(0xfff0e0, 0x5a3820, 0.25);
  scene.add(rimLeft, rimRight, fill);

  /* ---------- instrument holders ---------- */
  // pivot: the turning point (the instrument's visual centre); holder shifts the model onto it.
  const pivot = new THREE.Group();
  scene.add(pivot);
  const holder = new THREE.Group();
  holder.position.set(-PIVOT.x, -PIVOT.y, -PIVOT.z);
  pivot.add(holder);

  /* ---------- post-processing ---------- */
  const target = new THREE.WebGLRenderTarget(1, 1, { type: THREE.HalfFloatType, samples: 4 });
  const composer = new EffectComposer(renderer, target);
  composer.addPass(new RenderPass(scene, camera));
  const bokeh = new BokehPass(scene, camera, { focus: 270, aperture: 0, maxblur: 0.006 });
  bokeh.enabled = false;
  if (dof) composer.addPass(bokeh);
  composer.addPass(new OutputPass());

  // Depth of field: blur per cm away from the focus distance; 0 switches it off.
  function setDepthOfField(focus, aperture) {
    bokeh.enabled = dof && aperture > 1e-6;
    bokeh.uniforms.focus.value = focus;
    bokeh.uniforms.aperture.value = aperture;
  }

  const sizeListeners = [];
  function resize() {
    const w = container.clientWidth, h = container.clientHeight;
    renderer.setSize(w, h, false);
    composer.setSize(w, h);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    sizeListeners.forEach((f) => f(w, h));
  }
  window.addEventListener('resize', resize);

  return {
    renderer, scene, camera, pivot, holder, composer, resize, setDepthOfField,
    render: () => composer.render(),
    onResize: (f) => sizeListeners.push(f),
  };
}

// Angle of one screen pixel (radians per pixel ≈ cm per pixel at 1 cm away), used to keep
// the thin strings visible from far away.
export function pixelAngle(camera, height) {
  return (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2)) / height;
}
