// Scroll-driven playback of the tar fall (assets/saz/seq/NNN.webp: 81 frames
// at equal angle steps, built by sequence.py from the 17 key frames).
// The canvas sits in a sticky stage; scrolling through the tall .sequence
// section maps linearly to a position in the frames. Only one frame is ever
// drawn (no cross-fade, which looked ghostly); with frames ~1° apart and an
// eased position, the instrument still turns smoothly at an even pace.
// Cinematic touches: the shown position eases towards the scroll position
// (inertia instead of hard steps) and the camera slowly pushes in.
const FRAME_COUNT = 81;
const FRAME_PATH = 'assets/saz/seq/';
// On wide screens the motion takes the middle third of the page width
// (page : motion = 3 : 1); on portrait phones that would be too small, so
// there it fills the screen. Height is always capped so black stays around it.
const WIDTH_SHARE = 1 / 3;
const HEIGHT_SHARE = 0.94;
const EDGE_FADE = { side: 0.24, top: 0.1, bottom: 0.2 }; // edges melt into the black
const EASE = 0.075; // share of the remaining distance covered per animation frame
const PUSH_IN = 0.06; // extra zoom by the last frame

const sequence = document.getElementById('sequence');
const canvas = document.getElementById('sequenceCanvas');
const poster = document.getElementById('sequencePoster');
const context = canvas.getContext('2d');

const frames = [];
let current = -1; // last drawn position, to skip redundant draws
let shown = 0; // eased position that is actually drawn
let pending = false;
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function frameUrl(index) {
  // The standalone test build (tools/build_standalone.py) embeds the frames
  if (window.SAZ_FRAMES) {
    return window.SAZ_FRAMES[index];
  }
  return FRAME_PATH + String(index).padStart(3, '0') + '.webp';
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

  const index = Math.round(position);
  const base = frames[index];
  if (!ready(base)) {
    return; // drawn again once this frame has loaded
  }
  current = position;

  const push = 1 + PUSH_IN * (position / (FRAME_COUNT - 1));
  const widthShare = canvas.width > canvas.height ? WIDTH_SHARE : HEIGHT_SHARE;
  const fit = Math.min(canvas.width * widthShare / base.naturalWidth,
    canvas.height * HEIGHT_SHARE / base.naturalHeight);
  const scale = fit * push;
  const w = base.naturalWidth * scale;
  const h = base.naturalHeight * scale;
  const x = (canvas.width - w) / 2;
  const y = (canvas.height - h) / 2;

  context.globalAlpha = 1;
  context.fillStyle = '#000';
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(base, x, y, w, h);
  fadeEdges(x, y, w, h);
  poster.classList.add('hidden'); // the canvas has taken over
}

function requestDraw() {
  if (!pending) {
    pending = true;
    requestAnimationFrame(draw);
  }
}

window.addEventListener('scroll', requestDraw, { passive: true });
window.addEventListener('resize', resize);

// First frame first, so the opening shot appears as soon as possible.
// Never wait forever: if it is slow or fails, start anyway after 4 s.
const firstFrame = Promise.race([
  loadFrame(0),
  new Promise(function (resolve) { setTimeout(resolve, 4000); })
]);
firstFrame.then(function () {
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
