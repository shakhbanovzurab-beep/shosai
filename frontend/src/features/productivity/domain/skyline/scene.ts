export const clamp01 = (v: number): number => Math.min(1, Math.max(0, v));
export const lerp = (a: number, b: number, t: number): number => a + (b - a) * t;
export const easeInOutCubic = (x: number): number => {
  const t = clamp01(x);
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
};
export const easeOutCubic = (x: number): number => 1 - (1 - clamp01(x)) ** 3;
export const smoothstep = (a: number, b: number, x: number): number => {
  const t = clamp01((x - a) / (b - a));
  return t * t * (3 - 2 * t);
};

/** Eases `cur[i]` toward `goal`, snapping once close. Returns whether it is still moving. */
export const approach = (cur: Float32Array, i: number, goal: number, k: number, snap: number): boolean => {
  const v = cur[i];
  if (v === goal) return false;
  cur[i] = Math.abs(goal - v) < snap ? goal : v + (goal - v) * k;
  return true;
};

/** Box height in grid units. Empty days are thin slabs; the busiest day is ~7.6 cells tall. */
export const barHeight = (count: number, max: number, scale = 1): number =>
  count > 0 && max > 0 ? 0.4 + (count / max) ** 0.85 * 7.2 * scale : 0.2;

/** Share of the morph each bar spends waiting — the wave sweeps oldest week → newest. */
export const WAVE = 0.42;

/** 0 → 1 as a bar rises during the morph. Every bar is flat at t=0 and fully up at t=1. */
export const riseAt = (t: number, week: number, weeks: number, day: number): number => {
  const d = (weeks > 1 ? week / (weeks - 1) : 0) * 0.36 + (day / 6) * 0.06;
  return easeOutCubic((t - d) / (1 - WAVE));
};

export const YAW_3D = Math.PI / 4;
export const ELEV_3D = (34 * Math.PI) / 180;
export const YAW_RANGE: [number, number] = [(8 * Math.PI) / 180, (82 * Math.PI) / 180];
export const ELEV_RANGE: [number, number] = [(18 * Math.PI) / 180, (62 * Math.PI) / 180];

export type Cam = { cs: number; sn: number; se: number; ce: number };

/**
 * e=0 looks straight down: x across, y down, height invisible — a plain heat map.
 * e=1 is the isometric corner view. Orbit offsets apply in proportion to e, so the
 * flat view never tilts.
 */
export const camera = (e: number, dYaw = 0, dElev = 0): Cam => {
  const yaw = Math.min(YAW_RANGE[1], Math.max(0, lerp(0, YAW_3D + dYaw, e)));
  const elev = lerp(Math.PI / 2, Math.min(ELEV_RANGE[1], Math.max(ELEV_RANGE[0], ELEV_3D + dElev)), e);
  return { cs: Math.cos(yaw), sn: Math.sin(yaw), se: Math.sin(elev), ce: Math.cos(elev) };
};

/** World (x = week, y = weekday, z = up) → screen, before scale/offset. */
export const project = (c: Cam, x: number, y: number, z: number): [number, number] => [
  x * c.cs - y * c.sn,
  (x * c.sn + y * c.cs) * c.se - z * c.ce,
];

export const pointInQuad = (p: Float32Array, o: number, x: number, y: number): boolean => {
  let sign = 0;
  for (let k = 0; k < 4; k++) {
    const ax = p[o + k * 2];
    const ay = p[o + k * 2 + 1];
    const bx = p[o + ((k + 1) % 4) * 2];
    const by = p[o + ((k + 1) % 4) * 2 + 1];
    const cross = (bx - ax) * (y - ay) - (by - ay) * (x - ax);
    if (Math.abs(cross) < 1e-9) continue;
    const s = cross > 0 ? 1 : -1;
    if (sign === 0) sign = s;
    else if (s !== sign) return false;
  }
  return sign !== 0;
};
