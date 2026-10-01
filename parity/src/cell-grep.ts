// Отбор тестов проектом Playwright: проект (ячейка) берёт тесты со своим тегом.
//
// Выражения записаны литералами, а не собраны из имени ячейки: так их видно
// целиком и проверка кода не считает их построенными из внешних данных.
// Соответствие матрице — каждая ячейка здесь есть и совпадает только со своим
// тегом — проверяет cell-grep.test.ts.

export const CELL_GREP: Readonly<Record<string, RegExp>> = {
  "desktop-light-ru": /@desktop-light-ru(?![\w-])/,
  "desktop-dark-ru": /@desktop-dark-ru(?![\w-])/,
  "mobile-light-ru": /@mobile-light-ru(?![\w-])/,
  "mobile-dark-ru": /@mobile-dark-ru(?![\w-])/,
  "desktop-light-en": /@desktop-light-en(?![\w-])/,
  "desktop-dark-en": /@desktop-dark-en(?![\w-])/,
  "mobile-light-en": /@mobile-light-en(?![\w-])/,
  "mobile-dark-en": /@mobile-dark-en(?![\w-])/,
  "desktop-light-ar": /@desktop-light-ar(?![\w-])/,
  "mobile-light-ar": /@mobile-light-ar(?![\w-])/,
  "desktop-light-de": /@desktop-light-de(?![\w-])/,
  "mobile-light-de": /@mobile-light-de(?![\w-])/,
  "desktop-light-es": /@desktop-light-es(?![\w-])/,
  "mobile-light-es": /@mobile-light-es(?![\w-])/,
  "desktop-light-fr": /@desktop-light-fr(?![\w-])/,
  "mobile-light-fr": /@mobile-light-fr(?![\w-])/,
  "desktop-light-hi": /@desktop-light-hi(?![\w-])/,
  "mobile-light-hi": /@mobile-light-hi(?![\w-])/,
  "desktop-light-id": /@desktop-light-id(?![\w-])/,
  "mobile-light-id": /@mobile-light-id(?![\w-])/,
  "desktop-light-it": /@desktop-light-it(?![\w-])/,
  "mobile-light-it": /@mobile-light-it(?![\w-])/,
  "desktop-light-ja": /@desktop-light-ja(?![\w-])/,
  "mobile-light-ja": /@mobile-light-ja(?![\w-])/,
  "desktop-light-ko": /@desktop-light-ko(?![\w-])/,
  "mobile-light-ko": /@mobile-light-ko(?![\w-])/,
  "desktop-light-pt": /@desktop-light-pt(?![\w-])/,
  "mobile-light-pt": /@mobile-light-pt(?![\w-])/,
  "desktop-light-th": /@desktop-light-th(?![\w-])/,
  "mobile-light-th": /@mobile-light-th(?![\w-])/,
  "desktop-light-tr": /@desktop-light-tr(?![\w-])/,
  "mobile-light-tr": /@mobile-light-tr(?![\w-])/,
  "desktop-light-vi": /@desktop-light-vi(?![\w-])/,
  "mobile-light-vi": /@mobile-light-vi(?![\w-])/,
  "desktop-light-zh": /@desktop-light-zh(?![\w-])/,
  "mobile-light-zh": /@mobile-light-zh(?![\w-])/,
};

export function cellGrep(cellName: string): RegExp {
  const pattern = CELL_GREP[cellName];
  if (pattern === undefined) throw new Error(`Нет выражения отбора для ячейки ${cellName} (src/cell-grep.ts)`);
  return pattern;
}
