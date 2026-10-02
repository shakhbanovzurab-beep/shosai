/**
 * Геометрия фирменного знака Whisperer: сетка 3×3 жёлтых плиток со скруглёнными
 * углами и буквами W H I S P E R E R. Один источник для экранного логотипа и
 * для знака в выгружаемых файлах — две рисовалки разъехались бы.
 */

/** Сторона плитки в системе координат знака. */
export const MARK_TILE = 30;
/** Зазор между плитками. */
const MARK_GAP = 5;
/** viewBox знака: −2 по краям, чтобы обводка плиток не срезалась. */
export const MARK_VIEW_MIN = -2;
export const MARK_VIEW_SIZE = 104;

export const MARK_FONT = '"Arial Black", "Helvetica Neue", Arial, sans-serif';
/** Фирменные литералы знака — темой не управляются. */
export const MARK_INK = "#0A0A0A";
export const MARK_FILL = "#FFE000";

/** Пропорции округляются до сотых, как в исходном SVG знака: без двоичного мусора дробей. */
const round2 = (value: number): number => Math.round(value * 100) / 100;

export const MARK_RADIUS = round2(MARK_TILE * 0.16); // 4.8
export const MARK_TILE_STROKE = round2(MARK_TILE * 0.07); // 2.1
export const MARK_FONT_SIZE = round2(MARK_TILE * 0.62); // 18.6
export const MARK_TEXT_STROKE = round2(MARK_FONT_SIZE * 0.045); // 0.84

export interface MarkTile {
  readonly letter: string;
  /** Левый верхний угол плитки. */
  readonly x: number;
  readonly y: number;
}

const WORD = [
  ["W", "H", "I"],
  ["S", "P", "E"],
  ["R", "E", "R"],
] as const;

/** Девять плиток слева направо, сверху вниз. */
export const MARK_TILES: readonly MarkTile[] = WORD.flatMap((row, rowIndex) =>
  row.map((letter, column) => ({
    letter,
    x: column * (MARK_TILE + MARK_GAP),
    y: rowIndex * (MARK_TILE + MARK_GAP),
  })),
);
