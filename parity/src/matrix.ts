// Матрица съёмки: ячейка — вьюпорт × тема × язык.
//
// Полная матрица — 8 ячеек: компьютер и телефон, светлая и тёмная тема, ru и en.
// Основное состояние экрана снимается во всех восьми, мелкая вариация — в одной
// (ru, компьютер, светлая). Прогон по остальным 14 языкам — светлая тема на
// компьютере и телефоне, для одного насыщенного текстом экрана (план D2 §2).

export type ViewportName = "desktop" | "mobile";
export type Theme = "light" | "dark";
export type Scope = "full" | "single";

export interface Cell {
  /** Имя ячейки и проекта Playwright: `desktop-light-ru`. */
  readonly name: string;
  readonly viewport: ViewportName;
  readonly theme: Theme;
  readonly language: string;
}

export const VIEWPORTS: Readonly<Record<ViewportName, { width: number; height: number; touch: boolean }>> = {
  desktop: { width: 1440, height: 900, touch: false },
  // Мобильная раскладка черновика — до 860 px включительно.
  mobile: { width: 390, height: 844, touch: true },
};

/** Языки черновика; ru и en — языки полной матрицы. */
export const MATRIX_LANGUAGES: readonly string[] = ["ru", "en"];
export const SWEEP_LANGUAGES: readonly string[] = [
  "ar", "de", "es", "fr", "hi", "id", "it", "ja", "ko", "pt", "th", "tr", "vi", "zh",
];
export const SINGLE_CELL: Cell = cell("desktop", "light", "ru");

function cell(viewport: ViewportName, theme: Theme, language: string): Cell {
  return { name: `${viewport}-${theme}-${language}`, viewport, theme, language };
}

const VIEWPORT_NAMES: readonly ViewportName[] = ["desktop", "mobile"];
const THEMES: readonly Theme[] = ["light", "dark"];

/** Все ячейки: полная матрица и прогон по языкам. */
export function allCells(): Cell[] {
  const full = MATRIX_LANGUAGES.flatMap((language) =>
    VIEWPORT_NAMES.flatMap((viewport) => THEMES.map((theme) => cell(viewport, theme, language))),
  );
  const sweep = SWEEP_LANGUAGES.flatMap((language) => VIEWPORT_NAMES.map((viewport) => cell(viewport, "light", language)));
  return [...full, ...sweep];
}

/**
 * Ячейки состояния. `languages` — языки, на которых у состояния есть фикстура:
 * full — все сочетания вьюпорта и темы на этих языках матрицы; single — одна
 * ячейка, светлая тема, первый из вьюпортов и языков; sweep — плюс языки прогона.
 */
export function cellsFor(
  scope: Scope,
  languages: readonly string[],
  sweep: boolean,
  viewports: readonly ViewportName[] = VIEWPORT_NAMES,
): Cell[] {
  const matrix = languages.filter((language) => MATRIX_LANGUAGES.includes(language));
  const base =
    scope === "full"
      ? matrix.flatMap((language) => viewports.flatMap((viewport) => THEMES.map((theme) => cell(viewport, theme, language))))
      : [cell(viewports[0] ?? "desktop", "light", languages[0] ?? "ru")];
  if (!sweep) return base;
  return [...base, ...SWEEP_LANGUAGES.flatMap((language) => VIEWPORT_NAMES.map((viewport) => cell(viewport, "light", language)))];
}

/** Тег теста для ячейки: проект Playwright выбирает тесты своей ячейки по нему. */
export function cellTag(cellName: string): string {
  return `@${cellName}`;
}

/** Локаль браузера для языка: числа и даты Intl форматирует по ней. */
export function browserLocale(language: string): string {
  const regional: Readonly<Record<string, string>> = { ru: "ru-RU", en: "en-US", pt: "pt-BR", zh: "zh-TW" };
  return regional[language] ?? language;
}
