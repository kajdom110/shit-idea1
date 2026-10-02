// Single source of truth for every measurement of the tar, in centimetres.
//
// Axes: x = width (to the player's right when facing the skin), y = length (bottom of
// the kaseh = 0, head = up), z = depth (skin side = +z, the skin plane is z = 0).
//
// Sources, marked on each value:
//   std   – common Persian tar measurements
//   F1    – the user's front photo (full instrument, dark studio)
//   R4    – reference: body from the front (white background)
//   R5    – reference: head and pegs, end-on
//   R6    – reference: whole instrument, three-quarter rear
//   R2/R3 – reference: fingerboard close-up / heel close-up
// Ratios measured from the photos are recorded in docs/tar-3d/SPEC.md, section 5.

export const TOTAL_LENGTH = 95; // std

export const BODY = {
  length: 38, // F1 0.39, R6 0.41 of total length
  waistY: 20.5, // R4: the kaseh takes 0.53 of the body length

  kaseh: {
    width: 23, // F1 0.247 of total length; R4 body length / width = 1.45
    depth: 19, // R6 depth / body length ≈ 0.5, user asked for a deep bowl
    widestAt: 0.45, // fraction of kaseh length from the bottom (F1, R4)
    deepestAt: 0.42, // R6: deepest point a little below the widest
  },
  naghareh: {
    width: 18, // F1 0.72, R4 0.85 of the kaseh width → 0.78
    depth: 14, // shallower than the kaseh (R6)
    widestAt: 0.5, // fraction of the naghareh length from the waist
  },
  waistWidth: 13, // R4 0.62, F1 0.47 of the kaseh width → 0.57

  // Rounded top of the naghareh rises a little past the body length; the neck covers it.
  topY: 38.6,
  // Cross-section of the bowl is a superellipse: 2 = plain ellipse, higher = fuller back (R6).
  sectionExponent: 2.3,
  // Soft blend between the two lobes at the waist (cm).
  waistBlend: 1.6,

  rim: {
    width: 1.3, // wooden lip around the skin openings (R4)
    lipHeight: 0.25, // the wooden top stands this far above the skin (skin plane z = 0)
    filletRadius: 0.4, // rounded outer edge where the top meets the bowl wall
    inlayWidth: 0.45, // khatam band around each skin opening (F1)
  },
  skin: {
    border: 2.4, // wood from the outline to the skin at the widest points (F1: about 2.1–2.4)
    bottomGap: 2.2, // wood below the lower opening, above the tailpiece seat
    topY: 36.6, // the upper opening ends under the end of the fingerboard (F1)
    tipOverlap: 0.4, // the two heart tips pass each other by this much at the waist
    tipWidth: 0.06, // half-width of each heart at its tip
  },
  valley: {
    // carved diagonal groove on the back between the two bowls (R6)
    angleDeg: 25, // from horizontal, seen from the back
    depth: 1.8,
    width: 3.2,
  },
};

export const NECK = {
  bottomY: BODY.length, // the neck leaves the body at its top
  boardEndY: 36.2, // the fingerboard runs down onto the naghareh, just over the upper skin (F1)
  nutY: TOTAL_LENGTH - 13, // = 82; the head is 13 cm (see HEAD.height)
  widthAtNut: 3.3, // F1 / R4 relative to the kaseh width
  widthAtBody: 3.7,
  depthAtNut: 2.6, // R6: back of the neck below the top of the neck wood
  depthAtBody: 3.0,
  topZ: 0.6, // top of the neck wood (the fingerboard sits on it)
  sectionExponent: 2.2, // rounded D section
  cornerRadius: 0.2, // rounded top edges of the neck wood
  fingerboard: {
    thickness: 0.25,
    centreStrip: 0.9, // dark wood strip between the two bone strips (R2, F1)
    bevel: 0.03,
  },
  nut: { height: 0.45, length: 0.6, radius: 0.12, slots: 6 },
};

export const HEEL = {
  // pointed tongue running from the neck down the back of the naghareh (R3, R6)
  length: 10, // below the top of the body
  startY: 42, // the back of the neck starts to thicken here, above the body (R6)
  neckBulge: 0.6, // extra depth of the neck back where it reaches the body
  tipWidth: 1.2,
  thicknessTop: 0.5, // stand-off from the bowl where the neck meets it (matches neckBulge)
  thicknessMid: 1.0,
  thicknessTip: 0.8, // R3: the nose stays thick and rounded
  noseLength: 1.2, // rounded end of the tongue
};

export const HEAD = {
  height: TOTAL_LENGTH - NECK.nutY, // = 13 (F1: 0.134 of total length)
  width: 4.0, // F1: slightly wider than the neck at the nut
  depth: 3.4,
  slot: { width: 1.6, top: 1.5, bottom: 11.5 }, // from the top of the head (R5)
  wall: 0.6,
};

// Pegs: three each side, staggered (R5). `at` is the distance from the top of the head
// as a fraction of its height; side −1 = left (−x), +1 = right (+x).
export const PEGS = {
  knobDiameter: 3.2,
  knobLength: 2.6,
  collarDiameter: 1.6,
  shaftDiameter: 1.0,
  shaftTipDiameter: 0.75,
  reach: 5.2, // how far the knob end stands out from the head wall (F1)
  layout: [
    { side: -1, at: 0.29, string: 1 },
    { side: +1, at: 0.32, string: 2 },
    { side: +1, at: 0.49, string: 3 },
    { side: -1, at: 0.59, string: 4 },
    { side: -1, at: 0.82, string: 5 },
    { side: +1, at: 0.9, string: 6 },
  ],
};

export const SCALE_LENGTH = 68; // std 66–69; nut to bridge
export const BRIDGE = {
  y: NECK.nutY - SCALE_LENGTH, // = 14 cm above the bottom of the kaseh (F1/R4: 0.32–0.37 of the body)
  width: 5.4, // R4
  height: 1.0,
  thickness: 0.5,
  footWidth: 1.4, // two feet with an arch between them
};

export const TAILPIECE = {
  width: 2.6,
  length: 4.5, // runs down over the bottom of the rim (F1, R4)
  thickness: 0.4,
};

// Six strings in three courses. Gauges are diameters in cm.
export const STRINGS = {
  spanAtNut: 1.9, // outer string to outer string
  spanAtBridge: 3.4,
  gauges: [0.025, 0.025, 0.03, 0.03, 0.035, 0.05],
  wound: [false, false, false, false, false, true], // the low course has one wound bronze string
};

export const FRETS = {
  strandDiameter: 0.08, // gut strand (R2)
  strands: 4, // turns per fret
  strandsLite: 2, // turns per fret on the light quality level
  jitter: 0.02, // hand-tied turns are never perfectly even (cm)
  knotRadius: 0.11, // knot on the bass side of the neck (R2)
  tailLength: 0.35,
  nailHead: 0.09, // radius of the nail heads where a fret cannot wrap the back (R3)
};

// Pivot of the whole instrument: the visual centre of its bounding box, so it turns
// evenly about any axis.
export const PIVOT = { x: 0, y: TOTAL_LENGTH / 2, z: -BODY.kaseh.depth / 2 + 1.5 };

// Quality levels: one switch controls mesh density, texture size and shadow quality.
export const QUALITY = {
  high: { bodyStations: 220, bodyRadial: 144, fretTurns: FRETS.strands, texture: 2048, shadow: 2048 },
  lite: { bodyStations: 120, bodyRadial: 72, fretTurns: FRETS.strandsLite, texture: 1024, shadow: 1024 },
};
