// Free rotation in every direction (desktop): drag left/right to turn the instrument about the
// vertical, up/down to tip it towards or away from you. Rotations are kept as a quaternion
// applied in screen space, so there is no gimbal lock and no limit in any direction.
// After letting go it coasts briefly, and after a pause — or as soon as the page scrolls —
// it glides back to the pose of the current scroll scene.
import * as THREE from 'three';

const X = new THREE.Vector3(1, 0, 0), Y = new THREE.Vector3(0, 1, 0);
const IDENTITY = new THREE.Quaternion();

export function createRotationControls(element, { speed = 0.0065, returnAfter = 2.5 } = {}) {
  const user = new THREE.Quaternion();
  const q = new THREE.Quaternion();
  let dragging = false, lastX = 0, lastY = 0, lastT = 0, idle = Infinity;
  const vel = { x: 0, y: 0 }; // radians per second, so coasting is the same at any frame rate

  function turn(ax, ay) {
    if (ax) user.premultiply(q.setFromAxisAngle(Y, ax));
    if (ay) user.premultiply(q.setFromAxisAngle(X, ay));
    user.normalize();
  }

  element.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;
    dragging = true;
    lastX = e.clientX; lastY = e.clientY; lastT = e.timeStamp;
    vel.x = vel.y = 0;
    element.setPointerCapture(e.pointerId);
    element.classList.add('is-dragging');
  });
  element.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    const dx = (e.clientX - lastX) * speed, dy = (e.clientY - lastY) * speed;
    const dt = Math.max((e.timeStamp - lastT) / 1000, 1 / 240);
    lastX = e.clientX; lastY = e.clientY; lastT = e.timeStamp;
    turn(dx, dy);
    // smoothed speed of the hand, used for the coast after letting go
    vel.x = vel.x * 0.5 + (dx / dt) * 0.5;
    vel.y = vel.y * 0.5 + (dy / dt) * 0.5;
    idle = 0;
  });
  const end = (e) => {
    if (!dragging) return;
    dragging = false;
    idle = 0;
    // a hand that stopped before letting go should not coast
    if (e && e.timeStamp - lastT > 80) vel.x = vel.y = 0;
    const max = 6; // rad/s
    vel.x = Math.max(-max, Math.min(max, vel.x));
    vel.y = Math.max(-max, Math.min(max, vel.y));
    element.classList.remove('is-dragging');
    if (e && element.hasPointerCapture(e.pointerId)) element.releasePointerCapture(e.pointerId);
  };
  element.addEventListener('pointerup', end);
  element.addEventListener('pointercancel', end);
  element.addEventListener('dblclick', () => { idle = returnAfter; vel.x = vel.y = 0; });

  // Arrow keys turn it too, when the canvas has focus.
  element.addEventListener('keydown', (e) => {
    const step = 0.12;
    const map = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] };
    if (!map[e.key]) return;
    e.preventDefault();
    turn(...map[e.key]);
    idle = 0;
  });

  // Advances inertia and the glide home; returns true while anything is still moving.
  function update(dt, { scrolling = false } = {}) {
    if (dragging) return true;
    let active = false;
    if (Math.abs(vel.x) + Math.abs(vel.y) > 1e-3) {
      turn(vel.x * dt, vel.y * dt);
      const k = Math.exp(-dt * 6);
      vel.x *= k; vel.y *= k;
      active = true;
    }
    idle += dt;
    if ((idle > returnAfter || scrolling) && user.angleTo(IDENTITY) > 1e-4) {
      user.slerp(IDENTITY, 1 - Math.exp(-dt * (scrolling ? 4 : 2.2)));
      active = true;
    }
    return active;
  }

  return { quaternion: user, update, isDragging: () => dragging };
}
