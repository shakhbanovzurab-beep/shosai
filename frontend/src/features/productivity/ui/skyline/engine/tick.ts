import { approach } from "../../../domain/skyline/scene";
import { draw } from "./draw";
import type { Engine } from "./state";

const tick = (E: Engine, now: number) => {
  E.raf = 0;
  const dt = Math.min(0.05, Math.max(0, (now - E.last) / 1000));
  E.last = now;
  const rate = (speed: number) => (E.reduced ? 1 : 1 - Math.exp(-dt * speed));
  let moving = false;

  if (E.t !== E.target) {
    const step = E.reduced ? 1 : (dt * 1000) / Math.max(1, E.cfg.current.duration);
    E.t = E.target > E.t ? Math.min(E.target, E.t + step) : Math.max(E.target, E.t - step);
    moving = true;
  }

  const ko = rate(12);
  E.yaw += (E.yawGoal - E.yaw) * ko;
  E.elev += (E.elevGoal - E.elev) * ko;
  if (Math.abs(E.yawGoal - E.yaw) > 1e-4 || Math.abs(E.elevGoal - E.elev) > 1e-4) moving = true;
  else {
    E.yaw = E.yawGoal;
    E.elev = E.elevGoal;
  }

  const kc = rate(7);
  for (let k = 0; k < 15; k++) if (approach(E.col, k, E.colGoal[k], kc, 0.4)) moving = true;

  const kh = rate(16);
  const kd = rate(10);
  const leg = E.cfg.current.legendLevel;
  for (let i = 0; i < E.n; i++) {
    if (approach(E.hover, i, i === E.activeIdx ? 1 : 0, kh, 0.003)) moving = true;
    if (approach(E.dim, i, leg >= 0 && E.lv[i] !== leg ? 1 : 0, kd, 0.003)) moving = true;
  }

  draw(E);
  if (moving) E.raf = requestAnimationFrame((ts) => tick(E, ts));
};

export const kick = (E: Engine) => {
  if (E.raf) return;
  E.last = performance.now();
  E.raf = requestAnimationFrame((ts) => tick(E, ts));
};

export const orbitCursor = (E: Engine) => (E.cfg.current.orbit && E.target === 1 ? "grab" : "default");

/** The active day is the hovered one, else the pinned one (tap, click or keyboard). */
export const refreshActive = (E: Engine) => {
  const next = E.hovered >= 0 ? E.hovered : E.pinned;
  if (next === E.activeIdx) return;
  E.activeIdx = next;
  E.cfg.current.setActive(next);
  kick(E);
};

/** Follows the requested view once the chart has scrolled into sight. */
export const setTarget = (E: Engine) => {
  const goal = E.cfg.current.target;
  if (!E.entered || goal === E.target) return;
  E.target = goal;
  if (goal === 0) {
    E.yawGoal = 0;
    E.elevGoal = 0;
  }
  E.canvas.style.cursor = orbitCursor(E);
  kick(E);
};
