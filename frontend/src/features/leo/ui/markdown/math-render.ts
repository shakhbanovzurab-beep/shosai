import "katex/dist/katex.min.css";

import katex, { type KatexOptions } from "katex";

/*
 * Формулы ответа Leo: KaTeX строит разметку прямо в узле страницы, без строки HTML. Командам, которые ведут наружу
 * или задают свою разметку (`\href`, `\url`, `\htmlClass`, `\includegraphics`), он не доверяет и рисует их как
 * ошибку; размеры и раскрытие макросов ограничены, чтобы формула не раздула страницу.
 */
export const MATH_OPTIONS = {
  throwOnError: false,
  trust: false,
  strict: "ignore",
  output: "htmlAndMathml",
  maxSize: 20,
  maxExpand: 200,
  errorColor: "var(--destructive)",
} satisfies KatexOptions;

/** Формула в узел: в строке или блоком; прежнее содержимое узла заменяется. */
export function renderMath(tex: string, element: HTMLElement, display: boolean) {
  katex.render(tex, element, { ...MATH_OPTIONS, displayMode: display });
}
