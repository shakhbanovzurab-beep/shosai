import { mixRGB, rgbaString } from "../../../domain/skyline/colors";
import { type Cam, smoothstep } from "../../../domain/skyline/scene";
import type { Engine } from "./state";

export type Frame = {
  e: number;
  cam: Cam;
  s: number;
  w: number;
  off: number;
  lift: number;
  px: (x: number, y: number) => number;
  py: (x: number, y: number, z: number) => number;
};

/**
 * Labels run along the top and left in 2D, along the front edge in 3D. They fade, never pop. The month and weekday
 * names are in the interface language; the chart itself stays left to right (see contribution-skyline.tsx).
 */
const drawLabels = (E: Engine, f: Frame) => {
  const { ctx, W } = E;
  const { px, py, off, e } = f;
  const muted = mixRGB(E.bg, E.fg, 0.55);
  ctx.font = E.font;
  const a2 = 1 - smoothstep(0, 0.4, e);
  const a3 = smoothstep(0.62, 1, e);
  if (a2 > 0.004) {
    ctx.fillStyle = rgbaString(muted, a2);
    ctx.textAlign = "left";
    ctx.textBaseline = "bottom";
    let edge = -Infinity;
    for (const m of E.months) {
      const x = px(m.week + off, -0.3);
      const tw = ctx.measureText(m.label).width;
      if (x < edge || x + tw > W) continue;
      ctx.fillText(m.label, x, py(m.week + off, -0.3, 0) - 3);
      edge = x + tw + 6;
    }
    ctx.textAlign = "right";
    ctx.textBaseline = "middle";
    if (E.gutter > 0) {
      for (const r of E.weekdayRows) ctx.fillText(r.label, px(0, r.day + 0.5) - 6, py(0, r.day + 0.5, 0));
    }
  }
  if (a3 > 0.004) {
    ctx.fillStyle = rgbaString(muted, a3);
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    let edge = -Infinity;
    for (const m of E.months) {
      const x = px(m.week + 0.5, 7.3);
      const tw = ctx.measureText(m.label).width;
      if (x < edge || x + tw > W) continue;
      ctx.fillText(m.label, x, py(m.week + 0.5, 7.3, 0) + 2);
      edge = x + tw + 10;
    }
  }
};

/** The tooltip rides the active cell through morphs and orbits. */
const placeTooltip = (E: Engine, f: Frame) => {
  const i = E.activeIdx;
  if (i < 0 || i >= E.n) return;
  const { px, py, off, w } = f;
  const z = E.zs[i] + E.hover[i] * f.lift;
  const x0 = E.wk[i] + off;
  const y0 = E.dy[i] + off;
  const tx = px(E.wk[i] + 0.5, E.dy[i] + 0.5);
  const ty = Math.min(py(x0, y0, z), py(x0 + w, y0, z), py(x0, y0 + w, z));
  const half = E.tipW / 2;
  const cx = Math.min(E.W - half - 2, Math.max(half + 2, tx));
  E.tip.style.transform = `translate(${(cx - half).toFixed(1)}px,${(ty - 8).toFixed(1)}px) translateY(-100%)`;
  E.tip.style.setProperty("--arrow", `${(tx - cx + half).toFixed(1)}px`);
};

export const drawOverlay = (E: Engine, f: Frame) => {
  drawLabels(E, f);
  placeTooltip(E, f);
};
