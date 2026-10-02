// Solid (3D) procedural wood for MeshPhysicalMaterial.
//
// The colour is a function of each point's position inside the piece, not of a picture
// stretched over the surface: growth rings run round an axis along the grain, warped by
// noise, with thin dark latewood lines, open pores and broad figure. A bowl carved from such
// a block shows arcs on its back and straight stripes on its flat top, and the pattern is
// continuous across every edge — there is nothing to tear, stretch or seam when it turns.
import * as THREE from 'three';

const GLSL_PARS = /* glsl */ `
varying vec3 vWoodPos;
uniform vec3 woodLight;
uniform vec3 woodDark;
uniform vec3 woodLine;
uniform vec2 woodAxis;
uniform float woodFreq;
uniform float woodWarp;
uniform float woodPore;
uniform float woodFigure;
uniform float woodBump;

float wHash(vec3 p) {
  p = fract(p * 0.3183099 + vec3(0.71, 0.113, 0.419));
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}
float wNoise(vec3 x) {
  vec3 i = floor(x), f = fract(x);
  f = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(mix(wHash(i), wHash(i + vec3(1, 0, 0)), f.x), mix(wHash(i + vec3(0, 1, 0)), wHash(i + vec3(1, 1, 0)), f.x), f.y),
    mix(mix(wHash(i + vec3(0, 0, 1)), wHash(i + vec3(1, 0, 1)), f.x), mix(wHash(i + vec3(0, 1, 1)), wHash(i + vec3(1, 1, 1)), f.x), f.y),
    f.z);
}
float wFbm(vec3 p) {
  float s = 0.0, a = 0.5;
  for (int i = 0; i < 4; i++) { s += a * wNoise(p); p = p * 2.03 + 0.17; a *= 0.5; }
  return s;
}
// x: tone (0 light … 1 dark), y: latewood line, z: pore
vec3 woodPattern(vec3 p) {
  // grain runs along y: noise is stretched along it
  vec3 g = vec3(p.x, p.y * 0.12, p.z);
  float warp = (wFbm(g * 0.45) - 0.5) * woodWarp;
  float r = length(p.xz - woodAxis) + warp;
  float ring = fract(r * woodFreq);
  float late = smoothstep(0.45, 1.0, ring);
  float line = smoothstep(0.9, 0.97, ring) * (1.0 - smoothstep(0.985, 1.0, ring));
  float pore = smoothstep(0.74, 0.92, wNoise(vec3(p.x * 34.0, p.y * 0.9, p.z * 34.0))) * woodPore;
  float figure = (wFbm(g * vec3(1.1, 1.6, 1.1)) - 0.5) * woodFigure;
  return vec3(clamp(late * 0.75 + figure, 0.0, 1.0), line, pore);
}
`;

export function makeWood(params, base = {}) {
  const mat = new THREE.MeshPhysicalMaterial({ color: 0xffffff, side: THREE.DoubleSide, ...base });
  const u = {
    woodLight: { value: new THREE.Color(params.light) },
    woodDark: { value: new THREE.Color(params.dark) },
    woodLine: { value: new THREE.Color(params.line) },
    woodAxis: { value: new THREE.Vector2(...(params.axis || [0, 0])) },
    woodFreq: { value: params.freq ?? 1.6 },
    woodWarp: { value: params.warp ?? 0.6 },
    woodPore: { value: params.pore ?? 0.6 },
    woodFigure: { value: params.figure ?? 0.5 },
    woodBump: { value: params.bump ?? 0.02 },
  };
  mat.userData.wood = u;
  mat.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, u);
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vWoodPos;')
      .replace('#include <begin_vertex>', '#include <begin_vertex>\nvWoodPos = position;');
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', '#include <common>\n' + GLSL_PARS)
      .replace('#include <map_fragment>', `#include <map_fragment>
        vec3 wPat = woodPattern(vWoodPos);
        vec3 wCol = mix(woodLight, woodDark, wPat.x);
        wCol = mix(wCol, woodLine, wPat.y * 0.75);
        wCol *= 1.0 - wPat.z * 0.45;
        diffuseColor.rgb *= wCol;`)
      .replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
        roughnessFactor = clamp(roughnessFactor * (1.0 + wPat.z * 0.35 + wPat.y * 0.1), 0.0, 1.0);`)
      .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
        {
          // pores and latewood lines are very slightly sunk into the surface
          float wH = (-wPat.y * 0.5 - wPat.z) * woodBump;
          vec3 sx = dFdx(-vViewPosition), sy = dFdy(-vViewPosition);
          vec3 r1 = cross(sy, normal), r2 = cross(normal, sx);
          float det = dot(sx, r1) * faceDirection;
          vec3 grad = sign(det) * (dFdx(wH) * r1 + dFdy(wH) * r2);
          normal = normalize(abs(det) * normal - grad);
        }`);
  };
  mat.customProgramCacheKey = () => 'tar-wood';
  return mat;
}
