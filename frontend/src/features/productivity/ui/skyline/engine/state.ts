import type { SceneCells } from "../../../domain/skyline/cells";
import { BG_FALLBACK, FG_FALLBACK, type RGB } from "../../../domain/skyline/colors";
import type { ContributionDay } from "../../../domain/skyline/contributions";
import type { SkylineModel } from "../../../domain/skyline/stats";

/** Everything the render loop reads from React, refreshed every render so it never goes stale. */
export type EngineConfig = {
  model: SkylineModel;
  duration: number;
  heightScale: number;
  orbit: boolean;
  legendLevel: number;
  locale: string;
  target: 0 | 1;
  onCellClick?: (day: ContributionDay) => void;
  setActive: (i: number) => void;
  setWidth: (w: number) => void;
  setSwatches: (update: (prev: string[]) => string[]) => void;
  setAnnounce: (text: string) => void;
  describe: (i: number) => string;
};

export type EngineElements = {
  root: HTMLElement;
  stage: HTMLDivElement;
  canvas: HTMLCanvasElement;
  tip: HTMLDivElement;
  ctx: CanvasRenderingContext2D;
};

export type Engine = EngineElements &
  SceneCells & {
    cfg: { current: EngineConfig };
    reduced: boolean;
    // morph: t is linear time 0 (2D) → 1 (3D); the camera eases it, the bars wave it
    t: number;
    target: number;
    entered: boolean;
    // orbit offsets, eased toward their goals
    yaw: number;
    elev: number;
    yawGoal: number;
    elevGoal: number;
    // layout
    W: number;
    H2: number;
    H3: number;
    Hmax: number;
    lastH: number;
    dpr: number;
    gutter: number;
    labelW: number;
    font: string;
    // colours: [empty, l1, l2, l3, l4] × rgb, eased toward the goal
    col: Float32Array;
    colGoal: Float32Array;
    colReady: boolean;
    fg: RGB;
    bg: RGB;
    // interaction (hovered and pinned live in SceneCells)
    activeIdx: number;
    tipW: number;
    raf: number;
    last: number;
  };

export const createEngine = (els: EngineElements, cfg: { current: EngineConfig }, reduced: boolean): Engine => ({
  ...els,
  cfg,
  reduced,
  t: 0,
  target: 0,
  entered: false,
  yaw: 0,
  elev: 0,
  yawGoal: 0,
  elevGoal: 0,
  W: 0,
  H2: 0,
  H3: 0,
  Hmax: 0,
  lastH: -1,
  dpr: 1,
  gutter: 30,
  labelW: 30,
  font: "10px sans-serif",
  col: new Float32Array(15),
  colGoal: new Float32Array(15),
  colReady: false,
  fg: FG_FALLBACK,
  bg: BG_FALLBACK,
  n: 0,
  weeks: 0,
  wk: new Float32Array(0),
  dy: new Float32Array(0),
  lv: new Uint8Array(0),
  hgt: new Float32Array(0),
  zs: new Float32Array(0),
  hover: new Float32Array(0),
  dim: new Float32Array(0),
  polys: new Float32Array(0),
  faces: new Uint8Array(0),
  order: [],
  months: [],
  weekdayRows: [],
  hovered: -1,
  pinned: -1,
  activeIdx: -1,
  tipW: 0,
  raf: 0,
  last: 0,
});
