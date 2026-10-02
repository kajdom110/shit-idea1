// Entry point: builds the instrument. Each phase swaps a block-model part for the real one;
// the block model from phase 1 stands in for the parts not built yet.
import * as THREE from 'three';
import { QUALITY } from './dimensions.js';
import { buildGreybox } from './geometry/greybox.js';
import { buildBody } from './geometry/body.js';
import { buildHeel } from './geometry/heel.js';
import { buildNeck } from './geometry/neck.js';
import { buildFrets } from './geometry/fretwraps.js';

export function buildInstrument(materials, level = 'high') {
  const quality = QUALITY[level];
  const { root, parts } = buildGreybox(materials, { skip: ['body', 'skin', 'heel', 'neck', 'frets'] });
  const add = (g) => { parts[g.name] = g; root.add(g); };

  // Phase 2: body, skin and heel
  const { body, skin } = buildBody(materials, quality);
  const skinGroup = new THREE.Group();
  skinGroup.name = 'skin';
  skinGroup.add(skin);
  add(body);
  add(skinGroup);
  add(buildHeel(materials));

  // Phase 3: neck, fingerboard, nut and frets
  add(buildNeck(materials));
  add(buildFrets(materials, quality));

  return { root, parts };
}
