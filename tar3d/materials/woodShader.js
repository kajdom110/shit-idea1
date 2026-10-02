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
uniform vec2 woodTilt;
uniform float woodFreq;
uniform float woodWarp;
uniform float woodPore;
uniform float woodFigure;
uniform float woodBump;
uniform float woodFiber;
uniform float woodBias;
uniform float woodLineAmount;
uniform float woodLateAmount;

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
// Fades detail that would be finer than a pixel, so pores and fibres never sparkle.
float woodDetailFade(vec3 p) {
  return 1.0 - smoothstep(0.004, 0.02, length(fwidth(p)));
}
// x: tone (0 light … 1 dark), y: latewood line, z: pore
vec3 woodPattern(vec3 p) {
  // The log bends only gently over its length: low-frequency warp only, so each growth line
  // stays one clean, smooth curve (higher-frequency warp made jagged, contour-map lines).
  float warp = (wFbm(vec3(p.x * 0.08, p.y * 0.035, p.z * 0.08)) - 0.5) * woodWarp
             + (wFbm(vec3(p.x * 0.25, p.y * 0.02, p.z * 0.25) + 3.1) - 0.5) * woodWarp * 0.25;
  // The log's axis is never exactly parallel to the carved bowl: a slight tilt turns would-be
  // concentric circles on the back into long, stretched arches, as on real carved bowls.
  float r = length(p.xz - woodAxis - p.y * woodTilt) + warp;
  // Years of different width: a smooth, always increasing function of the radius (with a slow
  // drift along the log), so lines never wobble or cross but are unevenly spaced.
  float rr = r * woodFreq;
  float years = rr + 1.8 * (wNoise(vec3(rr * 0.13, 1.7, 3.3)) - 0.5) + 0.7 * (wNoise(vec3(rr * 0.45, p.y * 0.015, 9.1)) - 0.5);
  // a few tenths of a millimetre of jitter: real growth lines have slightly ragged edges
  float ring = fract(years + (wNoise(vec3(p.x * 6.0, p.y * 0.3, p.z * 6.0)) - 0.5) * 0.08);
  // each year's latewood line has its own strength: some lines strong, many faint
  float yearHash = fract(sin(floor(years) * 12.9898) * 43758.5453);
  float lineStrength = 0.25 + 0.75 * yearHash * yearHash;
  // earlywood is light; the wood darkens through the year into the latewood line,
  // then the next year starts light again
  float late = smoothstep(0.35, 0.92, ring);
  float aa = clamp(fwidth(years) * 1.5, 0.0, 0.5); // softens lines that get close to a pixel apart
  float line = smoothstep(0.86 - aa, 0.95, ring) * (1.0 - smoothstep(0.985 - aa, 1.0, ring)) * lineStrength;
  // ring-porous wood: the dark line is made of rows of open pores, so it reads as fine dashes
  // along the grain rather than a smooth printed band (averaged out where it gets too small to see)
  float poreRow = wNoise(vec3(p.x * 22.0, p.y * 0.7, p.z * 22.0));
  line *= mix(1.0, mix(0.35, 1.35, poreRow), woodDetailFade(p * 0.6));
  // ring-porous wood: the few visible pores sit in the light earlywood
  float pore = smoothstep(0.75, 0.92, wNoise(vec3(p.x * 34.0, p.y * 0.9, p.z * 34.0))) * woodPore * woodDetailFade(p) * (1.0 - late);
  // very gentle colour drift along the grain; no blotches
  float figure = (wFbm(vec3(p.x * 0.6, p.y * 0.03, p.z * 0.6) + 11.0) - 0.5) * woodFigure;
  return vec3(clamp(late * woodLateAmount + figure + woodBias, 0.0, 1.0), line, pore);
}
`;

export function makeWood(params, base = {}) {
  const mat = new THREE.MeshPhysicalMaterial({ color: 0xffffff, side: THREE.DoubleSide, ...base });
  const u = {
    woodLight: { value: new THREE.Color(params.light) },
    woodDark: { value: new THREE.Color(params.dark) },
    woodLine: { value: new THREE.Color(params.line) },
    woodAxis: { value: new THREE.Vector2(...(params.axis || [0, 0])) },
    woodTilt: { value: new THREE.Vector2(...(params.tilt || [0, 0])) }, // axis drift per cm along the grain
    woodFreq: { value: params.freq ?? 1.6 },
    woodWarp: { value: params.warp ?? 0.6 },
    woodPore: { value: params.pore ?? 0.6 },
    woodFigure: { value: params.figure ?? 0.5 },
    woodBump: { value: params.bump ?? 0.02 },
    woodFiber: { value: params.fiber ?? 0.3 },
    woodBias: { value: params.bias ?? 0.1 }, // shifts the balance of light and dark wood
    woodLineAmount: { value: params.lineAmount ?? 0.15 }, // strength of the thin latewood lines
    woodLateAmount: { value: params.lateAmount ?? 0.4 }, // light-to-dark swing across each ring
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
        // line darkness varies from ring to ring, as in real wood
        float wLineVar = 0.75 + 0.5 * wNoise(vWoodPos * vec3(0.6, 0.02, 0.6) + 5.0);
        wCol = mix(wCol, woodLine, clamp(wPat.y * woodLineAmount * wLineVar, 0.0, 1.0));
        wCol *= 1.0 - wPat.z * 0.45;
        // fine fibres along the grain: raw wood, not a painted surface
        float wFade = woodDetailFade(vWoodPos);
        float wFib = wNoise(vec3(vWoodPos.x * 60.0, vWoodPos.y * 1.4, vWoodPos.z * 60.0));
        wCol *= 1.0 + (wFib - 0.5) * woodFiber * wFade;
        diffuseColor.rgb *= wCol;`)
      .replace('#include <roughnessmap_fragment>', `#include <roughnessmap_fragment>
        // an even satin finish: only a faint variation, no patches
        float wWear = wFbm(vWoodPos * vec3(0.18, 0.06, 0.18));
        roughnessFactor = clamp(roughnessFactor * (1.0 + wPat.z * 0.2) * mix(0.95, 1.05, wWear), 0.0, 1.0);`)
      .replace('#include <normal_fragment_maps>', `#include <normal_fragment_maps>
        {
          // under varnish the grain lines are colour only, not grooves: only the fibres have a faint relief
          float wH = (wFib - 0.5) * woodFiber * 0.3 * wFade * woodBump;
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
