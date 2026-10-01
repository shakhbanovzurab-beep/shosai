// Режим прогона и допуски сравнения.
//
//  baseline — снять черновик и записать эталон (Playwright с --update-snapshots=all);
//  verify   — снять черновик ещё раз и сравнить с эталоном без допуска: так
//             доказывается, что съёмка повторяется (критерий D2);
//  compare  — снять v2 и сравнить с эталоном с допуском паритета.

import type { State } from "../states/types.ts";

export type Mode = "baseline" | "verify" | "compare";

export function parseMode(value: string | undefined): Mode {
  if (value === "baseline" || value === "verify" || value === "compare") return value;
  throw new Error(`PARITY_MODE должен быть baseline, verify или compare, получено: ${value ?? "ничего"}`);
}

/** Допуск паритета: цветовой порог 0.1 и не больше 0,1 % отличающихся пикселей. */
export const PARITY_THRESHOLD = 0.1;
export const PARITY_MAX_DIFF_RATIO = 0.001;

export interface ScreenshotTolerance {
  readonly threshold: number;
  readonly maxDiffPixels?: number;
  readonly maxDiffPixelRatio?: number;
}

export function toleranceFor(mode: Mode, state: State): ScreenshotTolerance {
  if (mode !== "compare") return { threshold: 0, maxDiffPixels: 0 };
  return { threshold: PARITY_THRESHOLD, maxDiffPixelRatio: state.tolerance?.maxDiffPixelRatio ?? PARITY_MAX_DIFF_RATIO };
}
