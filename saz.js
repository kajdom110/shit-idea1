// Tipping-over animation of the tar, matching the reference sheet:
// 17 frames from 0° to 80° in 5° steps, ending on the floor with dust.
const instrument = document.getElementById('sazInstrument');
const shadow = document.getElementById('sazShadow');
const dustLayer = document.getElementById('sazDust');
const labelFrame = document.getElementById('sazLabelFrame');
const labelAngle = document.getElementById('sazLabelAngle');
const playButton = document.getElementById('sazPlay');
const frameSlider = document.getElementById('sazFrame');

const SVG_NS = 'http://www.w3.org/2000/svg';
const PIVOT_X = 200;
const PIVOT_Y = 420;
const BOWL_RADIUS = 60; // the lower bowl rolls on the floor while tipping
const FLOOR_Y = 480;
const MAX_ANGLE = 80;
const GRAVITY = 16; // rad/s², sets how fast it topples
const BOUNCE = 0.3; // fraction of speed kept after hitting the floor

let angle = 0; // degrees
let velocity = 0; // rad/s
let lastTime = 0;
let running = false;
let dust = [];
let looping = false;

function toPersianDigits(value, width) {
  return String(value).padStart(width, '0').replace(/\d/g, function (d) {
    return '۰۱۲۳۴۵۶۷۸۹'[d];
  });
}

function render() {
  const roll = BOWL_RADIUS * angle * Math.PI / 180;
  instrument.setAttribute('transform',
    'translate(' + roll + ' 0) rotate(' + angle + ' ' + PIVOT_X + ' ' + PIVOT_Y + ')');
  shadow.setAttribute('cx', PIVOT_X + roll + angle * 1.2);
  shadow.setAttribute('rx', 70 + angle * 1.6);

  const frame = Math.round(angle / 5);
  labelFrame.textContent = toPersianDigits(frame, 2);
  labelAngle.textContent = (frame === 0 ? '' : '−') + toPersianDigits(frame * 5, 1) + '°';
  if (!running) {
    frameSlider.value = frame;
  }
}

function spawnDust(strength) {
  const roll = BOWL_RADIUS * MAX_ANGLE * Math.PI / 180;
  const sources = [PIVOT_X + roll + 30, PIVOT_X + roll + 120, PIVOT_X + roll + 260];
  sources.forEach(function (x) {
    for (let i = 0; i < 14; i++) {
      const particle = document.createElementNS(SVG_NS, 'circle');
      dustLayer.appendChild(particle);
      dust.push({
        el: particle,
        x: x + (Math.random() - 0.5) * 40,
        y: FLOOR_Y - Math.random() * 6,
        vx: (Math.random() - 0.3) * 90 * strength,
        vy: -Math.random() * 70 * strength,
        r: 1.5 + Math.random() * 2.5,
        life: 1
      });
    }
  });
}

function updateDust(dt) {
  dust = dust.filter(function (p) {
    p.life -= dt * 0.8;
    if (p.life <= 0) {
      p.el.remove();
      return false;
    }
    p.vy += 60 * dt;
    p.vx *= 1 - dt * 1.5;
    p.x += p.vx * dt;
    p.y = Math.min(p.y + p.vy * dt, FLOOR_Y + 4);
    p.el.setAttribute('cx', p.x);
    p.el.setAttribute('cy', p.y);
    p.el.setAttribute('r', p.r * (1.6 - p.life * 0.6));
    p.el.setAttribute('opacity', p.life * 0.7);
    return true;
  });
}

function clearDust() {
  dust.forEach(function (p) { p.el.remove(); });
  dust = [];
}

function step(time) {
  const dt = Math.min((time - lastTime) / 1000, 0.033);
  lastTime = time;

  if (running) {
    // Inverted pendulum: the further it leans, the faster it falls
    const radians = angle * Math.PI / 180;
    velocity += GRAVITY * Math.sin(radians + 0.02) * dt;
    angle += velocity * dt * 180 / Math.PI;

    if (angle >= MAX_ANGLE) {
      angle = MAX_ANGLE;
      if (velocity > 1) {
        spawnDust(Math.min(velocity / 6, 1.4));
      }
      velocity = -velocity * BOUNCE;
      if (Math.abs(velocity) < 0.4) {
        velocity = 0;
        running = false;
      }
    }
    render();
  }

  updateDust(dt);
  if (running || dust.length > 0) {
    requestAnimationFrame(step);
  } else {
    looping = false;
  }
}

function play() {
  clearDust();
  angle = 0;
  velocity = 0;
  running = true;
  render();
  if (looping) {
    return;
  }
  looping = true;
  requestAnimationFrame(function (time) {
    lastTime = time;
    requestAnimationFrame(step);
  });
}

playButton.addEventListener('click', play);

frameSlider.addEventListener('input', function () {
  running = false;
  clearDust();
  angle = Number(frameSlider.value) * 5;
  render();
});

if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
  render();
} else {
  setTimeout(play, 600);
}
