// Entry point: builds the instrument. Each phase swaps a block-model part for the real one;
// until then the block model from phase 1 stands in.
import { buildGreybox } from './geometry/greybox.js';

export function buildInstrument(materials) {
  return buildGreybox(materials);
}
