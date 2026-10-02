// Fret positions of the tar, from the intervals each fret sounds above the open string.
// The set follows the common Persian layout and includes the koron (quarter-flat) frets.
import { NECK, SCALE_LENGTH } from './dimensions.js';

// Cents above the open string, 25 frets (the count seen on the front photo F1).
export const FRET_CENTS = [
  90, 135, 204, 294, 342, 408, 498, 588, 636, 702, 792, 840, 906, 996, 1044, 1110, 1200,
  1290, 1335, 1404, 1494, 1542, 1608, 1698, 1788,
];

// Distance from the nut along the string: L · (1 − 2^(−cents/1200)).
export const fretDistance = (cents) => SCALE_LENGTH * (1 - Math.pow(2, -cents / 1200));

// y position of every fret in instrument space.
export const FRET_Y = FRET_CENTS.map((c) => NECK.nutY - fretDistance(c));
