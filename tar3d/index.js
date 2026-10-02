// Entry point: builds the whole instrument from its parts.
import * as THREE from 'three';
import { QUALITY } from './dimensions.js';
import { buildBody } from './geometry/body.js';
import { buildHeel } from './geometry/heel.js';
import { buildNeck } from './geometry/neck.js';
import { buildFrets } from './geometry/fretwraps.js';
import { buildHead } from './geometry/head.js';
import { buildPegs } from './geometry/pegs.js';
import { buildHardware, buildStrings } from './geometry/hardware.js';

export function buildInstrument(materials, level = 'high') {
  const quality = QUALITY[level];
  const root = new THREE.Group();
  root.name = 'tar';
  const parts = {};
  const add = (g) => { parts[g.name] = g; root.add(g); };

  const { body, skin } = buildBody(materials, quality);
  const skinGroup = new THREE.Group();
  skinGroup.name = 'skin';
  skinGroup.add(skin);
  add(body);
  add(skinGroup);
  add(buildHeel(materials));
  add(buildNeck(materials));
  add(buildFrets(materials, quality));
  add(buildHead(materials));
  add(buildPegs(materials));
  add(buildHardware(materials));
  add(buildStrings(materials));

  return { root, parts };
}
