import { extent } from "../../../domain/skyline/cells";
import { rgbaString, rgbString } from "../../../domain/skyline/colors";
import { camera, easeInOutCubic, lerp, riseAt } from "../../../domain/skyline/scene";
import { drawOverlay, type Frame } from "./overlay";
import type { Engine } from "./state";

const quadPath = (ctx: CanvasRenderingContext2D, p: Float32Array, o: number, r: number) => {
  if (r < 0.3) {
    ctx.moveTo(p[o], p[o + 1]);
    ctx.lineTo(p[o + 2], p[o + 3]);
    ctx.lineTo(p[o + 4], p[o + 5]);
    ctx.lineTo(p[o + 6], p[o + 7]);
    ctx.closePath();
    return;
  }
  ctx.moveTo((p[o + 6] + p[o]) / 2, (p[o + 7] + p[o + 1]) / 2);
  for (let k = 0; k < 4; k++) {
    const b = (k + 1) % 4;
    ctx.arcTo(p[o + k * 2], p[o + k * 2 + 1], p[o + b * 2], p[o + b * 2 + 1], r);
  }
  ctx.closePath();
};

/** Places the scene for this frame: camera, scale and the world → screen mapping. */
const frame = (E: Engine): Frame => {
  const e = easeInOutCubic(E.t);
  const cam = camera(e, E.yaw, E.elev);
  const Hc = lerp(E.H2, E.H3, e);
  if (Math.abs(Hc - E.lastH) > 0.2) {
    E.stage.style.height = `${Hc.toFixed(1)}px`;
    E.lastH = Hc;
  }
  for (let i = 0; i < E.n; i++) E.zs[i] = riseAt(E.t, E.wk[i], E.weeks, E.dy[i]) * E.hgt[i];
  const b = extent(E, cam, e, false);
  const pad = lerp(2, 20, e);
  const left = pad + E.gutter * (1 - e);
  const top = pad + 20 * (1 - e);
  const aw = E.W - left - pad;
  const ah = Hc - top - pad;
  const bw = Math.max(1e-6, b.maxx - b.minx);
  const bh = Math.max(1e-6, b.maxy - b.miny);
  const s = Math.min(aw / bw, ah / bh);
  const ox = left + (aw - bw * s) / 2 - b.minx * s;
  const oy = top + (ah - bh * s) / 2 - b.miny * s;
  const { cs, sn, se, ce } = cam;
  const w = lerp(0.78, 0.9, e);
  return {
    e,
    cam,
    s,
    w,
    off: (1 - w) / 2,
    lift: 0.7 * e,
    px: (x, y) => ox + (x * cs - y * sn) * s,
    py: (x, y, z) => oy + ((x * sn + y * cs) * se - z * ce) * s,
  };
};

/** Fills one cell's +y face, +x face and top, back to front. */
const drawCell = (E: Engine, f: Frame, i: number, radius: number, outline: number) => {
  const { ctx, polys: p, col } = E;
  const { px, py, w, off } = f;
  const x0 = E.wk[i] + off;
  const y0 = E.dy[i] + off;
  const x1 = x0 + w;
  const y1 = y0 + w;
  const z = E.zs[i] + E.hover[i] * f.lift;
  const o = i * 24;
  // top, then the +y face (left on screen), then the +x face (right on screen)
  const pts = [
    [x0, y0, z],
    [x1, y0, z],
    [x1, y1, z],
    [x0, y1, z],
    [x0, y1, 0],
    [x1, y1, 0],
    [x1, y1, z],
    [x0, y1, z],
    [x1, y0, 0],
    [x1, y1, 0],
    [x1, y1, z],
    [x1, y0, z],
  ];
  for (let k = 0; k < 12; k++) {
    p[o + k * 2] = px(pts[k][0], pts[k][1]);
    p[o + k * 2 + 1] = py(pts[k][0], pts[k][1], pts[k][2]);
  }
  const tall = z * f.cam.ce * f.s;
  let faces = 0;
  if (tall > 0.35 && w * f.cam.cs * f.s > 0.35) faces |= 1;
  if (tall > 0.35 && w * f.cam.sn * f.s > 0.35) faces |= 2;
  E.faces[i] = faces;

  const L = E.lv[i] * 3;
  let r = col[L];
  let g = col[L + 1];
  let b = col[L + 2];
  const d = E.dim[i];
  if (d > 0.002) {
    r += (col[0] - r) * 0.72 * d;
    g += (col[1] - g) * 0.72 * d;
    b += (col[2] - b) * 0.72 * d;
  }
  const hv = E.hover[i];
  if (hv > 0.002) {
    const m = 0.16 * hv;
    r += (E.fg[0] - r) * m;
    g += (E.fg[1] - g) * m;
    b += (E.fg[2] - b) * m;
  }
  if (faces & 1) {
    ctx.beginPath();
    quadPath(ctx, p, o + 8, 0);
    ctx.fillStyle = rgbString(r * 0.84, g * 0.84, b * 0.84);
    ctx.fill();
  }
  if (faces & 2) {
    ctx.beginPath();
    quadPath(ctx, p, o + 16, 0);
    ctx.fillStyle = rgbString(r * 0.68, g * 0.68, b * 0.68);
    ctx.fill();
  }
  ctx.beginPath();
  quadPath(ctx, p, o, radius);
  ctx.fillStyle = rgbString(r, g, b);
  ctx.fill();
  if (outline > 0.004) {
    ctx.strokeStyle = rgbaString(E.fg, outline);
    ctx.lineWidth = 1;
    ctx.stroke();
  }
  if (hv > 0.02) {
    ctx.strokeStyle = rgbaString(E.fg, 0.85 * hv);
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }
};

export const draw = (E: Engine) => {
  if (!E.W || !E.n) return;
  const f = frame(E);
  const { sn, cs } = f.cam;
  E.ctx.setTransform(E.dpr, 0, 0, E.dpr, 0, 0);
  E.ctx.clearRect(0, 0, E.W, E.Hmax);
  // Painter's order: larger depth is nearer the viewer, so draw ascending.
  E.order.sort((a, c) => (E.wk[a] - E.wk[c]) * sn + (E.dy[a] - E.dy[c]) * cs);
  const radius = lerp(0.17, 0.03, f.e) * f.s;
  const outline = (1 - f.e) * 0.07;
  for (let k = 0; k < E.n; k++) drawCell(E, f, E.order[k], radius, outline);
  drawOverlay(E, f);
};
