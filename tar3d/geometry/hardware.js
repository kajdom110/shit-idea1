// Bridge (kharak), tailpiece (simgir) and the six strings.
// Each string runs tailpiece → over the bridge → over the nut → into the slot of the head,
// where it winds a few turns round the shaft of its own peg.
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { RoundedBoxGeometry } from 'three/addons/geometries/RoundedBoxGeometry.js';
import { BODY, BRIDGE, TAILPIECE, STRINGS, PEGS } from '../dimensions.js';
import { lerp } from './util.js';
import { NUT_TOP } from './neck.js';
import { pegAxis } from './pegs.js';

const TOP_Z = BODY.rim.lipHeight;

function bridgeGeometry() {
  const hw = BRIDGE.width / 2, f = BRIDGE.footWidth, h = BRIDGE.height, b = 0.06;
  // Front view: two feet with an arch between them, a gently crowned top.
  const s = new THREE.Shape();
  s.moveTo(-hw + b, b);
  s.lineTo(-hw + f, b);
  s.quadraticCurveTo(0, h * 0.55, hw - f, b);
  s.lineTo(hw - b, b);
  s.lineTo(hw - b, h * 0.5);
  s.quadraticCurveTo(hw * 0.6, h - b, 0, h - b);
  s.quadraticCurveTo(-hw * 0.6, h - b, -hw + b, h * 0.5);
  s.lineTo(-hw + b, b);
  const g = new THREE.ExtrudeGeometry(s, { depth: BRIDGE.thickness - 2 * b, bevelEnabled: true, bevelThickness: b, bevelSize: b, bevelSegments: 2, curveSegments: 16 });
  // shape height → z, extrusion → −y; centre it on the bridge line
  g.rotateX(Math.PI / 2);
  g.translate(0, BRIDGE.y + BRIDGE.thickness / 2 - b, 0);
  return g;
}

// x of each string at a station, from its position at the bridge.
const atBridge = (() => {
  const c = STRINGS.spanAtBridge / 2 - STRINGS.pairGap / 2, g = STRINGS.pairGap / 2;
  return [-c - g, -c + g, -g, g, c - g, c + g];
})();
const scaled = (span) => atBridge.map((x) => (x * span) / STRINGS.spanAtBridge);

export function buildHardware(materials) {
  const group = new THREE.Group();
  group.name = 'hardware';

  const bridge = new THREE.Mesh(bridgeGeometry(), materials.horn);
  bridge.name = 'bridge';
  bridge.castShadow = true;
  group.add(bridge);

  const T = TAILPIECE;
  const tail = new THREE.Mesh(new RoundedBoxGeometry(T.width, T.length, T.thickness, 3, T.radius), materials.boneSmall);
  tail.position.set(0, T.y0 + T.length / 2, TOP_Z + T.thickness / 2);
  tail.name = 'tailpiece';
  tail.castShadow = true;
  group.add(tail);

  const pins = scaled(STRINGS.spanAtTail).map((x) => {
    const g = new THREE.CylinderGeometry(0.05, 0.05, 0.25, 8);
    g.rotateX(Math.PI / 2);
    g.translate(x, T.pinY, TOP_Z + T.thickness + 0.1);
    return g;
  });
  const pinMesh = new THREE.Mesh(mergeGeometries(pins), materials.metal);
  pinMesh.name = 'tailPins';
  group.add(pinMesh);
  return group;
}

export function buildStrings(materials) {
  const group = new THREE.Group();
  group.name = 'strings';
  const tailX = scaled(STRINGS.spanAtTail), nutX = scaled(STRINGS.spanAtNut);
  const zTail = TOP_Z + TAILPIECE.thickness + 0.12;
  const steel = [], bronze = [];

  for (let i = 0; i < 6; i++) {
    const r = STRINGS.gauges[i] / 2;
    const peg = PEGS.layout.find((p) => p.string === i + 1);
    const axis = pegAxis(peg);
    const wx = lerp(-0.45, 0.45, i / 5); // where it meets its shaft inside the slot

    const pts = [
      new THREE.Vector3(tailX[i], TAILPIECE.pinY, zTail),
      new THREE.Vector3(atBridge[i], BRIDGE.y, BRIDGE.height + r),
      new THREE.Vector3(nutX[i], NUT_TOP.y, NUT_TOP.z + r),
      new THREE.Vector3(wx, axis.y, axis.z + axis.r + r),
    ];
    const geos = [];
    for (let k = 0; k < pts.length - 1; k++) {
      geos.push(new THREE.TubeGeometry(new THREE.LineCurve3(pts[k], pts[k + 1]), 1, r, 6, false));
    }
    // Coil round the peg shaft, starting where the string arrives on top of it
    const coil = [];
    const turns = STRINGS.coilTurns, steps = turns * 16, rr = axis.r + r;
    const dir = i < 3 ? 1 : -1; // coils grow towards the middle of the slot
    for (let k = 0; k <= steps; k++) {
      const th = (k / steps) * turns * Math.PI * 2;
      coil.push(new THREE.Vector3(wx + dir * STRINGS.coilWidth * (k / steps), axis.y + rr * Math.sin(th), axis.z + rr * Math.cos(th)));
    }
    geos.push(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(coil), steps, r, 6, false));
    (STRINGS.wound[i] ? bronze : steel).push(mergeGeometries(geos));
  }

  const s = new THREE.Mesh(mergeGeometries(steel), materials.metal);
  s.name = 'steelStrings';
  group.add(s);
  if (bronze.length) {
    const b = new THREE.Mesh(mergeGeometries(bronze), materials.bronze || materials.metal);
    b.name = 'woundString';
    group.add(b);
  }
  return group;
}
