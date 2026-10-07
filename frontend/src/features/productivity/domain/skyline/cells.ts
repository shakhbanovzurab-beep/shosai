import { dayMs } from "./contributions";
import { barHeight, type Cam, lerp, pointInQuad, project } from "./scene";
import type { MonthLabel, SkylineModel } from "./stats";

/** The cells as flat typed arrays: what the render loop reads every frame. */
export type SceneCells = {
  n: number;
  weeks: number;
  wk: Float32Array;
  dy: Float32Array;
  lv: Uint8Array;
  hgt: Float32Array;
  zs: Float32Array;
  hover: Float32Array;
  dim: Float32Array;
  polys: Float32Array;
  faces: Uint8Array;
  order: number[];
  months: MonthLabel[];
  weekdayRows: { day: number; label: string }[];
  // interaction: the hovered and the pinned cell, -1 for none
  hovered: number;
  pinned: number;
};

/** Copies the model into the flat typed arrays. */
export const loadCells = (E: SceneCells, m: SkylineModel, heightScale: number, locale: string) => {
  const n = m.cells.length;
  E.n = n;
  E.weeks = m.weeks;
  if (E.wk.length !== n) {
    E.wk = new Float32Array(n);
    E.dy = new Float32Array(n);
    E.lv = new Uint8Array(n);
    E.hgt = new Float32Array(n);
    E.zs = new Float32Array(n);
    E.hover = new Float32Array(n);
    E.dim = new Float32Array(n);
    E.polys = new Float32Array(n * 24);
    E.faces = new Uint8Array(n);
    E.order = Array.from({ length: n }, (_, i) => i);
  }
  for (let i = 0; i < n; i++) {
    const c = m.cells[i];
    E.wk[i] = c.week;
    E.dy[i] = c.day;
    E.lv[i] = c.level;
    E.hgt[i] = barHeight(c.count, m.max, heightScale);
  }
  E.months = m.months;
  // Weekday names in the interface language, for every other row.
  const wf = new Intl.DateTimeFormat(locale, { weekday: "short", timeZone: "UTC" });
  E.weekdayRows = [];
  for (let d = 0; d < 7 && d < n; d++) {
    const ms = dayMs(m.cells[d].date);
    const dow = new Date(ms).getUTCDay();
    if (dow === 1 || dow === 3 || dow === 5) E.weekdayRows.push({ day: d, label: wf.format(ms) });
  }
  if (E.hovered >= n) E.hovered = -1;
  if (E.pinned >= n) E.pinned = -1;
};

/** Projected extent of the scene for camera e; `full` uses fully risen bars, else the current heights. */
export const extent = (E: SceneCells, cam: Cam, e: number, full: boolean) => {
  const w = lerp(0.78, 0.9, e);
  const off = (1 - w) / 2;
  let minx = Infinity;
  let maxx = -Infinity;
  let miny = Infinity;
  let maxy = -Infinity;
  const add = (x: number, y: number, z: number) => {
    const p = project(cam, x, y, z);
    if (p[0] < minx) minx = p[0];
    if (p[0] > maxx) maxx = p[0];
    if (p[1] < miny) miny = p[1];
    if (p[1] > maxy) maxy = p[1];
  };
  for (let i = 0; i < E.n; i++) {
    const x0 = E.wk[i] + off;
    const y0 = E.dy[i] + off;
    const z = full ? E.hgt[i] * e : E.zs[i];
    add(x0, y0, z);
    add(x0 + w, y0, z);
    add(x0, y0 + w, z);
    add(x0 + w, y0 + w, 0);
    add(x0, y0 + w, 0);
    add(x0 + w, y0, 0);
  }
  // room for the month labels that run along the front edge in 3D
  add(0, 7 + 1.5 * e, 0);
  add(E.weeks, 7 + 1.5 * e, 0);
  return { minx, maxx, miny, maxy };
};

/** The front-most cell under a screen point, from the polygons the last frame drew; -1 for none. */
export const hitCell = (E: SceneCells, x: number, y: number): number => {
  for (let k = E.n - 1; k >= 0; k--) {
    const i = E.order[k];
    const o = i * 24;
    if (pointInQuad(E.polys, o, x, y)) return i;
    if (E.faces[i] & 1 && pointInQuad(E.polys, o + 8, x, y)) return i;
    if (E.faces[i] & 2 && pointInQuad(E.polys, o + 16, x, y)) return i;
  }
  return -1;
};
