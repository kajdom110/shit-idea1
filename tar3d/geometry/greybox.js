// Phase 1 block model: every part as a simple shape at its true size and place, so the
// proportions of the whole instrument can be judged before any detail is built.
// Phases 2–4 replace these blocks one part at a time.
import * as THREE from 'three';
import { BODY, NECK, HEEL, HEAD, PEGS, BRIDGE, TAILPIECE, STRINGS, TOTAL_LENGTH } from '../dimensions.js';
import { FRET_Y } from '../frets.js';

const lerp = (a, b, t) => a + (b - a) * t;

// Half an ellipsoid: flat at the skin plane (z = 0), rounded towards −z.
function halfEllipsoid(w, len, depth, centreY, mat) {
  const g = new THREE.SphereGeometry(1, 48, 32, 0, Math.PI * 2, 0, Math.PI / 2);
  g.rotateX(-Math.PI / 2); // open side faces +z
  const m = new THREE.Mesh(g, mat);
  m.scale.set(w / 2, len / 2, depth);
  m.position.set(0, centreY, 0);
  return m;
}

export function buildGreybox(materials, { skip = [] } = {}) {
  const { wood, lightWood, darkWood, bone, skin, metal, gut, horn } = materials;
  const parts = {};
  const group = (name) => {
    const g = new THREE.Group();
    g.name = name;
    parts[name] = g;
    return g;
  };

  // Body
  const body = group('body');
  const kasehLen = BODY.waistY;
  const naghLen = BODY.length - BODY.waistY;
  body.add(halfEllipsoid(BODY.kaseh.width, kasehLen * 1.15, BODY.kaseh.depth, kasehLen * 0.5, wood));
  body.add(halfEllipsoid(BODY.naghareh.width, naghLen * 1.15, BODY.naghareh.depth, BODY.waistY + naghLen * 0.5, wood));

  // Skin openings as flat discs on the front
  const skinGroup = group('skin');
  [[BODY.kaseh.width * 0.72, kasehLen * 0.8, kasehLen * 0.48], [BODY.naghareh.width * 0.7, naghLen * 0.8, BODY.waistY + naghLen * 0.5]]
    .forEach(([w, h, y]) => {
      const d = new THREE.Mesh(new THREE.CircleGeometry(1, 48), skin);
      d.scale.set(w / 2, h / 2, 1);
      d.position.set(0, y, 0.01);
      skinGroup.add(d);
    });

  // Neck
  const neck = group('neck');
  const neckLen = NECK.nutY - NECK.bottomY;
  const neckMesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), lightWood);
  neckMesh.scale.set((NECK.widthAtNut + NECK.widthAtBody) / 2, neckLen, (NECK.depthAtNut + NECK.depthAtBody) / 2);
  neckMesh.position.set(0, NECK.bottomY + neckLen / 2, -neckMesh.scale.z / 2 + NECK.fingerboard.thickness + 0.6);
  neck.add(neckMesh);
  const board = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), bone);
  board.scale.set(NECK.widthAtNut, neckLen, NECK.fingerboard.thickness);
  board.position.set(0, NECK.bottomY + neckLen / 2, 0.6 + NECK.fingerboard.thickness / 2);
  neck.add(board);

  // Heel on the back of the naghareh
  const heel = group('heel');
  const heelMesh = new THREE.Mesh(new THREE.ConeGeometry(NECK.widthAtBody / 2, HEEL.length, 16), lightWood);
  heelMesh.rotation.x = Math.PI; // point downwards
  heelMesh.position.set(0, BODY.length - HEEL.length / 2, -BODY.naghareh.depth * 0.75);
  heel.add(heelMesh);

  // Frets: thin rings at the computed positions
  const frets = group('frets');
  FRET_Y.forEach((y) => {
    const t = (y - NECK.bottomY) / neckLen;
    const ring = new THREE.Mesh(new THREE.BoxGeometry(lerp(NECK.widthAtBody, NECK.widthAtNut, t) + 0.1, 0.12, 0.1), gut);
    ring.position.set(0, y, 0.6 + NECK.fingerboard.thickness + 0.05);
    frets.add(ring);
  });

  // Head
  const head = group('head');
  const headMesh = new THREE.Mesh(new THREE.BoxGeometry(HEAD.width, HEAD.height, HEAD.depth), darkWood);
  headMesh.position.set(0, NECK.nutY + HEAD.height / 2, 0.85 - HEAD.depth / 2);
  head.add(headMesh);

  // Pegs
  const pegs = group('pegs');
  PEGS.layout.forEach((p) => {
    const y = TOTAL_LENGTH - p.at * HEAD.height;
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(PEGS.shaftDiameter / 2, PEGS.shaftDiameter / 2, PEGS.reach, 16), darkWood);
    shaft.rotation.z = Math.PI / 2;
    shaft.position.set(p.side * (HEAD.width / 2 + PEGS.reach / 2), y, headMesh.position.z);
    const knob = new THREE.Mesh(new THREE.SphereGeometry(PEGS.knobDiameter / 2, 24, 16), darkWood);
    knob.scale.set(PEGS.knobLength / PEGS.knobDiameter, 1, 1);
    knob.position.set(p.side * (HEAD.width / 2 + PEGS.reach - PEGS.knobLength / 2), y, headMesh.position.z);
    pegs.add(shaft, knob);
  });

  // Bridge and tailpiece
  const hardware = group('hardware');
  const bridge = new THREE.Mesh(new THREE.BoxGeometry(BRIDGE.width, BRIDGE.thickness, BRIDGE.height), horn);
  bridge.position.set(0, BRIDGE.y, BRIDGE.height / 2);
  const tail = new THREE.Mesh(new THREE.BoxGeometry(TAILPIECE.width, TAILPIECE.length, TAILPIECE.thickness), bone);
  tail.position.set(0, TAILPIECE.length / 2 - 0.5, TAILPIECE.thickness / 2);
  hardware.add(bridge, tail);

  // Strings: straight lines from the tailpiece over the bridge and nut
  const strings = group('strings');
  const zNut = 0.6 + NECK.fingerboard.thickness + NECK.nut.height;
  for (let i = 0; i < 6; i++) {
    const u = i / 5 - 0.5;
    const pts = [
      new THREE.Vector3(u * TAILPIECE.width * 0.7, 1.5, TAILPIECE.thickness),
      new THREE.Vector3(u * STRINGS.spanAtBridge, BRIDGE.y, BRIDGE.height),
      new THREE.Vector3(u * STRINGS.spanAtNut, NECK.nutY, zNut),
    ];
    const g = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts, false, 'chordal'), 64, STRINGS.gauges[i] / 2, 6);
    strings.add(new THREE.Mesh(g, metal));
  }

  skip.forEach((name) => delete parts[name]);
  const root = new THREE.Group();
  Object.values(parts).forEach((p) => root.add(p));
  return { root, parts };
}
