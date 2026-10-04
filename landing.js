// Scroll-driven playback of the 17-frame tar fall (assets/saz/final/NN.webp).
// The canvas sits in a sticky stage; scrolling through the tall .sequence
// section maps to a position in the frames, and neighbouring frames are
// cross-faded so the motion stays smooth between the 17 drawings.
// Cinematic touches: the shown position eases towards the scroll position
// (inertia instead of hard steps) and the camera slowly pushes in.
const FRAME_COUNT = 17;
const FRAME_PATH = 'assets/saz/final/';
const FILL = 0.94; // share of the screen the frame may take; the rest stays black
const EDGE_FADE = { side: 0.24, top: 0.1, bottom: 0.2 }; // edges melt into the black
const EASE = 0.12; // share of the remaining distance covered per animation frame
const PUSH_IN = 0.06; // extra zoom by the last frame
const DISSOLVE = 0.3; // part of each step spent dissolving into the next frame

const sequence = document.getElementById('sequence');
const canvas = document.getElementById('sequenceCanvas');
const context = canvas.getContext('2d');

const frames = [];
let current = -1; // last drawn position, to skip redundant draws
let shown = 0; // eased position that is actually drawn
let pending = false;
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function frameUrl(index) {
  return FRAME_PATH + String(index).padStart(2, '0') + '.webp';
}

function loadFrame(index) {
  const image = new Image();
  image.decoding = 'async';
  image.src = frameUrl(index);
  frames[index] = image;
  return image.decode().catch(function () {}).then(function () { return image; });
}

function resize() {
  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  canvas.width = Math.round(canvas.clientWidth * ratio);
  canvas.height = Math.round(canvas.clientHeight * ratio);
  current = -1;
  requestDraw();
}

function scrollPosition() {
  const rect = sequence.getBoundingClientRect();
  const distance = rect.height - window.innerHeight;
  const progress = distance > 0 ? Math.min(Math.max(-rect.top / distance, 0), 1) : 0;
  return progress * (FRAME_COUNT - 1);
}

function ready(image) {
  return image && image.complete && image.naturalWidth > 0;
}

function fadeEdges(x, y, w, h) {
  const sides = [
    [x, y, x + w * EDGE_FADE.side, y, x, y, w * EDGE_FADE.side, h],
    [x + w, y, x + w * (1 - EDGE_FADE.side), y, x + w * (1 - EDGE_FADE.side), y, w * EDGE_FADE.side, h],
    [x, y, x, y + h * EDGE_FADE.top, x, y, w, h * EDGE_FADE.top],
    [x, y + h, x, y + h * (1 - EDGE_FADE.bottom), x, y + h * (1 - EDGE_FADE.bottom), w, h * EDGE_FADE.bottom]
  ];
  sides.forEach(function (s) {
    const gradient = context.createLinearGradient(s[0], s[1], s[2], s[3]);
    gradient.addColorStop(0, 'rgba(0, 0, 0, 1)');
    gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
    context.fillStyle = gradient;
    context.fillRect(s[4], s[5], s[6], s[7]);
  });

  // Soft spotlight falloff over the whole frame
  const vignette = context.createRadialGradient(
    x + w / 2, y + h * 0.55, Math.min(w, h) * 0.35,
    x + w / 2, y + h * 0.55, Math.max(w, h) * 0.75
  );
  vignette.addColorStop(0, 'rgba(0, 0, 0, 0)');
  vignette.addColorStop(1, 'rgba(0, 0, 0, 0.55)');
  context.fillStyle = vignette;
  context.fillRect(x, y, w, h);
}

function draw() {
  pending = false;
  const target = scrollPosition();
  shown = reduceMotion ? target : shown + (target - shown) * EASE;
  if (Math.abs(target - shown) < 0.002) {
    shown = target;
  } else {
    requestDraw(); // keep gliding towards the scroll position
  }
  const position = shown;
  if (Math.abs(position - current) < 0.001) {
    return;
  }

  // Hold each frame clean and dissolve only around the midpoint between two
  // frames, so stopping the scroll never leaves a double image for long
  const index = Math.floor(position);
  const step = position - index;
  const t = Math.min(Math.max((step - (0.5 - DISSOLVE / 2)) / DISSOLVE, 0), 1);
  const blend = t * t * (3 - 2 * t);
  const base = frames[index];
  const next = frames[Math.min(index + 1, FRAME_COUNT - 1)];
  if (!ready(base)) {
    return; // drawn again once this frame has loaded
  }
  current = position;

  const push = 1 + PUSH_IN * (position / (FRAME_COUNT - 1));
  const scale = Math.min(canvas.width / base.naturalWidth, canvas.height / base.naturalHeight) * FILL * push;
  const w = base.naturalWidth * scale;
  const h = base.naturalHeight * scale;
  const x = (canvas.width - w) / 2;
  const y = (canvas.height - h) / 2;

  context.globalAlpha = 1;
  context.fillStyle = '#000';
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(base, x, y, w, h);
  if (blend > 0 && ready(next)) {
    context.globalAlpha = blend;
    context.drawImage(next, x, y, w, h);
    context.globalAlpha = 1;
  }
  fadeEdges(x, y, w, h);
}

function requestDraw() {
  if (!pending) {
    pending = true;
    requestAnimationFrame(draw);
  }
}

window.addEventListener('scroll', requestDraw, { passive: true });
window.addEventListener('resize', resize);

// First frame first, so the opening shot appears as soon as possible
loadFrame(0).then(function () {
  shown = scrollPosition(); // reloads mid-page start where the page is
  resize();
  canvas.classList.add('visible');
  for (let i = 1; i < FRAME_COUNT; i++) {
    loadFrame(i).then(function () {
      current = -1;
      requestDraw();
    });
  }
});
