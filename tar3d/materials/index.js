// All materials of the tar. Every part is a physically based material lit by the same
// scene lights; nothing has lighting baked into it.
//
// Colour targets are the swatches in docs/tar-3d/SPEC.md, section 5.6 (honey mulberry,
// a little dark, as decided by the user).
import * as THREE from 'three';
import { makeWood } from './woodShader.js';
import { O, SKIN_RANGE } from '../geometry/body.js';
import { symmetricShape } from '../geometry/util.js';

const texURL = (name) => new URL('../textures/' + name, import.meta.url).href;

function loadTexture(loader, name, { srgb = true, repeat = [1, 1], aniso = 8 } = {}) {
  const t = loader.load(texURL(name));
  t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(...repeat);
  t.anisotropy = aniso;
  return t;
}

// Mask of the skin openings, softened at the edges: 1 well inside the skin, falling to 0
// outside. Used to darken the glued border of the skin, as on the reference photos.
function skinEdgeMask() {
  const [y0, y1] = SKIN_RANGE;
  let maxW = 0;
  for (let y = y0; y <= y1; y += 0.1) maxW = Math.max(maxW, O(y));
  const pad = 1;
  const bounds = { x0: -maxW - pad, y0: y0 - pad, w: 2 * (maxW + pad), h: y1 - y0 + 2 * pad };
  const W = 256, H = Math.round((W * bounds.h) / bounds.w);
  const c = document.createElement('canvas');
  c.width = W; c.height = H;
  const g = c.getContext('2d');
  g.fillStyle = '#000';
  g.fillRect(0, 0, W, H);
  g.filter = 'blur(5px)';
  g.fillStyle = '#fff';
  g.beginPath();
  symmetricShape(O, y0, y1, 300).forEach((p, i) => {
    const px = ((p.x - bounds.x0) / bounds.w) * W, py = (1 - (p.y - bounds.y0) / bounds.h) * H;
    if (i) g.lineTo(px, py); else g.moveTo(px, py);
  });
  g.closePath();
  g.fill();
  const tex = new THREE.CanvasTexture(c);
  tex.colorSpace = THREE.NoColorSpace;
  return { tex, bounds };
}

// Strings are a fraction of a millimetre thick, far less than a pixel from across the room,
// so they would flicker in and out. This keeps each string at least ~0.7 px wide on screen
// and fades it in proportion, which is how a thin wire really reads in a photograph.
export const stringUniforms = { pixelAngle: { value: 0.0005 } };
function makeString(base, radius) {
  const m = base.clone();
  m.transparent = true;
  m.onBeforeCompile = (shader) => {
    shader.uniforms.pixelAngle = stringUniforms.pixelAngle;
    shader.uniforms.stringRadius = { value: radius };
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nuniform float pixelAngle;\nuniform float stringRadius;\nvarying float vCover;')
      .replace('#include <begin_vertex>', `#include <begin_vertex>
        {
          float dist = max(1.0, -(modelViewMatrix * vec4(position, 1.0)).z);
          float want = 0.35 * pixelAngle * dist;
          transformed += objectNormal * max(0.0, want - stringRadius);
          vCover = clamp(stringRadius / want, 0.3, 1.0);
        }`);
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', '#include <common>\nvarying float vCover;')
      .replace('#include <alphamap_fragment>', '#include <alphamap_fragment>\ndiffuseColor.a *= vCover;');
  };
  m.customProgramCacheKey = () => 'tar-string';
  return m;
}

export function createMaterials({ anisotropy = 8, manager } = {}) {
  const loader = new THREE.TextureLoader(manager);
  const T = (name, opts) => loadTexture(loader, name, { aniso: anisotropy, ...opts });

  /* ---------- woods ---------- */
  const wood = makeWood(
    // kaseh and naghareh: honey-amber mulberry with thin, close, nearly straight grain lines and a
    // satin finish, matched to reference photo R7 (spec section 11)
    { light: '#a06e32', dark: '#663f25', line: '#341a0a', axis: [0, 9], tilt: [0.12, 0.22], freq: 2.6, warp: 1.2, pore: 0.15, figure: 0.1, bump: 0.025, fiber: 0.2, bias: 0.2, lineAmount: 0.6, lateAmount: 0.4 },
    { roughness: 0.42, clearcoat: 0.3, clearcoatRoughness: 0.32, envMapIntensity: 0.5, specularIntensity: 0.7 },
  );
  const lightWood = makeWood(
    // neck and heel: paler, straighter grain
    { light: '#b98a4c', dark: '#86592a', line: '#4f3115', axis: [0, -1.5], freq: 2.6, warp: 0.4, pore: 0.45, figure: 0.35, bump: 0.02 },
    { roughness: 0.5, clearcoat: 0.25, clearcoatRoughness: 0.4 },
  );
  const headWood = makeWood(
    // head: mid walnut (R5)
    { light: '#8c6242', dark: '#4f341f', line: '#2a1a0e', axis: [0, -0.8], freq: 2.0, warp: 0.5, pore: 0.5, figure: 0.4, bump: 0.02 },
    { roughness: 0.5, clearcoat: 0.25, clearcoatRoughness: 0.4 },
  );
  const pegWood = makeWood(
    // pegs: dark, turned — rings run round the peg's own axis
    { light: '#6e4829', dark: '#352011', line: '#1d1008', axis: [0, 0], freq: 3.0, warp: 0.25, pore: 0.3, figure: 0.3, bump: 0.015 },
    { roughness: 0.42, clearcoat: 0.35, clearcoatRoughness: 0.3 },
  );
  const boardWood = makeWood(
    // dark strip in the middle of the fingerboard (R2)
    { light: '#4c2c17', dark: '#26140a', line: '#120a05', axis: [0, -3], freq: 3.0, warp: 0.3, pore: 0.4, figure: 0.3, bump: 0.015 },
    { roughness: 0.45, clearcoat: 0.2, clearcoatRoughness: 0.4 },
  );
  const horn = makeWood(
    // bridge: polished horn, long amber streaks
    { light: '#a2723c', dark: '#4a2a12', line: '#2a160a', axis: [0, 0], freq: 0.8, warp: 1.5, pore: 0, figure: 0.9, bump: 0 },
    { roughness: 0.28, clearcoat: 0.6, clearcoatRoughness: 0.2 },
  );
  const lip = makeWood(
    // the unvarnished wooden lip round the skin: greyish brown (R7, about 117 86 76), matte
    { light: '#74594a', dark: '#574236', line: '#3e2e24', axis: [0, 9], freq: 2.6, warp: 0.35, pore: 0.3, figure: 0.2, bump: 0.02, fiber: 0.35, lineAmount: 0.3 },
    { roughness: 0.68, clearcoat: 0 },
  );
  const cavity = new THREE.MeshStandardMaterial({ color: '#150c07', roughness: 0.95, side: THREE.DoubleSide });

  /* ---------- skin ---------- */
  const skinRepeat = [1 / 36, 1 / 36]; // one 2048 px tile spans 36 cm: never repeats on the skin
  const skin = new THREE.MeshPhysicalMaterial({
    map: T('skin_albedo.webp', { repeat: skinRepeat }),
    bumpMap: T('skin_height.webp', { srgb: false, repeat: skinRepeat }),
    bumpScale: 0.6, // phase 7: 1.5 looked gritty at grazing angles
    roughness: 0.72,
    color: '#e2dacb', // slightly dims the albedo so the skin does not wash out under the key light
    sheen: 0.5, sheenRoughness: 0.7, sheenColor: new THREE.Color('#b8aa92'),
    side: THREE.DoubleSide,
  });
  const mask = skinEdgeMask();
  skin.onBeforeCompile = (shader) => {
    shader.uniforms.skinMask = { value: mask.tex };
    shader.uniforms.skinBounds = { value: new THREE.Vector4(mask.bounds.x0, mask.bounds.y0, mask.bounds.w, mask.bounds.h) };
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec2 vSkinPos;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvSkinPos = position.xy;');
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', '#include <common>\nvarying vec2 vSkinPos;\nuniform sampler2D skinMask;\nuniform vec4 skinBounds;')
      .replace('#include <map_fragment>', `#include <map_fragment>
        // R7: thin skin over the dark hollow reads slate-violet in the middle, lighter and
        // warmer where it lies over the wooden lip
        float skinEdge = texture2D(skinMask, (vSkinPos - skinBounds.xy) / skinBounds.zw).r;
        float glue = 1.0 - smoothstep(0.55, 0.92, skinEdge);
        float hollow = smoothstep(0.75, 1.0, skinEdge);
        diffuseColor.rgb *= mix(vec3(1.08, 1.0, 0.94), vec3(0.5, 0.5, 0.6), hollow);`)
      .replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
        roughnessFactor *= mix(1.0, 0.8, glue);`);
  };
  skin.customProgramCacheKey = () => 'tar-skin';

  /* ---------- bone, inlay, gut, metal ---------- */
  const boneRepeat = [1 / 6, 1 / 6];
  const bone = new THREE.MeshPhysicalMaterial({
    map: T('bone_albedo.webp', { repeat: boneRepeat }),
    bumpMap: T('bone_height.webp', { srgb: false, repeat: boneRepeat }),
    // the colour slightly dims the cream texture: under the studio key it otherwise reads as white plastic
    color: '#d6c9ae', bumpScale: 0.8, roughness: 0.42, clearcoat: 0.15, clearcoatRoughness: 0.4, side: THREE.DoubleSide,
  });
  // For small parts with 0–1 UVs per face (nut, tailpiece)
  const boneSmall = bone.clone();
  boneSmall.map = T('bone_albedo.webp', { repeat: [0.5, 0.5] });
  boneSmall.bumpMap = T('bone_height.webp', { srgb: false, repeat: [0.5, 0.5] });

  const inlayRepeat = [1 / 1.2, 1 / 1.2]; // 8 rows of triangles every 1.2 cm
  const inlay = new THREE.MeshPhysicalMaterial({
    map: T('khatam.webp', { repeat: inlayRepeat }),
    bumpMap: T('khatam_height.webp', { srgb: false, repeat: inlayRepeat }),
    bumpScale: 1, roughness: 0.4, clearcoat: 0.35, clearcoatRoughness: 0.3, side: THREE.DoubleSide,
  });

  const gut = new THREE.MeshPhysicalMaterial({
    map: T('gut.webp', { repeat: [120, 1] }),
    color: '#cfae6a', // straw, as on the reference close-ups
    roughness: 0.5, clearcoat: 0.2, clearcoatRoughness: 0.4,
  });

  const metal = new THREE.MeshPhysicalMaterial({ color: '#d4d4d2', metalness: 1, roughness: 0.25 });
  const bronze = new THREE.MeshPhysicalMaterial({ color: '#b48848', metalness: 1, roughness: 0.32 });
  const stringSteel = makeString(metal, 0.014);
  const stringBronze = makeString(bronze, 0.025);

  return { wood, lightWood, headWood, pegWood, boardWood, horn, lip, cavity, skin, bone, boneSmall, inlay, gut, metal, bronze, stringSteel, stringBronze };
}
