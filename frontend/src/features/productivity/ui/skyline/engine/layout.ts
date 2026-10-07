import { extent, loadCells } from "../../../domain/skyline/cells";
import { rgbString } from "../../../domain/skyline/colors";
import { camera } from "../../../domain/skyline/scene";
import { draw } from "./draw";
import type { Engine } from "./state";
import { readThemeColors } from "./theme";
import { kick } from "./tick";

/** Copies the model into the engine's flat typed arrays. */
export const load = (E: Engine) => {
  const { model, heightScale, locale } = E.cfg.current;
  loadCells(E, model, heightScale, locale);
};

/** Re-reads the theme preset and eases the cells toward its colours. */
export const retheme = (E: Engine) => {
  const theme = readThemeColors(E.root);
  E.fg = theme.fg;
  E.bg = theme.bg;
  E.font = theme.font;
  for (let k = 0; k < 5; k++) for (let ch = 0; ch < 3; ch++) E.colGoal[k * 3 + ch] = theme.levels[k][ch];
  if (!E.colReady || E.reduced) {
    E.col.set(E.colGoal);
    E.colReady = true;
  }
  E.ctx.font = E.font;
  E.labelW = Math.ceil(Math.max(20, ...E.weekdayRows.map((r) => E.ctx.measureText(r.label).width))) + 8;
  const sw = theme.levels.map((c) => rgbString(c[0], c[1], c[2]));
  E.cfg.current.setSwatches((prev) => (prev.join() === sw.join() ? prev : sw));
  kick(E);
};

export const relayout = (E: Engine) => {
  const W = Math.round(E.stage.clientWidth);
  if (!W || !E.n) return;
  E.W = W;
  // Narrow cards give the weekday names' column to the grid instead; rows get too tight to label.
  E.gutter = W < 520 ? 0 : E.labelW;
  E.dpr = Math.min(2, window.devicePixelRatio || 1);
  const b2 = extent(E, camera(0), 0, true);
  E.H2 = 24 + ((b2.maxy - b2.miny) / (b2.maxx - b2.minx)) * (W - E.gutter - 4);
  const b3 = extent(E, camera(1), 1, true);
  const natural = ((b3.maxy - b3.miny) / (b3.maxx - b3.minx)) * (W - 40) + 40;
  E.H3 = Math.max(Math.min(natural, W * 0.72, 620), Math.min(natural, 240));
  E.Hmax = Math.ceil(Math.max(E.H2, E.H3));
  E.canvas.width = Math.round(W * E.dpr);
  E.canvas.height = Math.round(E.Hmax * E.dpr);
  E.canvas.style.width = `${W}px`;
  E.canvas.style.height = `${E.Hmax}px`;
  E.lastH = -1;
  E.cfg.current.setWidth(W);
  draw(E);
};
