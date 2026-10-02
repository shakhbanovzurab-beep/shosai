/**
 * Шрифты интерфейса: 16 языков × 5 ролей (спека 084 черновика).
 *
 * Единственный источник правды о сопоставлении «язык × роль → семейства».
 * Из него `scripts/fonts/generate.ts` строит правила `core/styles/generated/
 * font-roles.css` и файлы `@font-face` в `fonts/`, а тесты сверяют их с ним.
 *
 * Роль, а не гарнитура: «с засечками» существует и для деванагари, и для
 * кандзи, просто называется каждый раз по-своему. Поэтому 80 сопоставлений на
 * 28 гарнитур, и ни одна роль ни одного языка не остаётся без своего лица.
 *
 * Первой в цепочке стоит гарнитура, которую мы раздаём сами и которая
 * покрывает письменность языка; системные идут запасом на случай, если файл
 * не доехал. Системная первой допустима только у роли `native`.
 */

/** Код языка платформы: совпадает с каталогами строк и с `wh.lang`. */
export const FONT_LOCALES = [
  "ru", "en", "de", "es", "pt", "fr", "it", "tr",
  "id", "vi", "ar", "hi", "th", "ja", "zh", "ko",
] as const;
export type FontLocale = (typeof FONT_LOCALES)[number];

/** Роли. Порядок значим: это порядок плиток выбора в кабинете. */
export const FONT_ROLES = ["whisperer", "sans", "serif", "native", "mono"] as const;
export type FontRole = (typeof FONT_ROLES)[number];

/** Фирменная роль: на документе ей соответствует отсутствие `data-font`. */
export const DEFAULT_FONT_ROLE: FontRole = "whisperer";

export interface FontDefinition {
  /** Цепочка `font-family` целиком; первое семейство и есть ответ «чем набрано». */
  readonly stack: string;
  /** Раздаваемые нами семейства из цепочки. Пусто у ролей на системных шрифтах. */
  readonly hosted: readonly string[];
}

/** Системная цепочка — общая для латинских и кириллических локалей. */
const SYSTEM_STACK =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

/** Фирменная пара. Глифов CJK, деванагари, тайского и арабского у неё нет. */
const BRAND_STACK = '"Onest", "PT Root UI"';

const role = (stack: string, hosted: readonly string[]): FontDefinition => ({ stack, hosted });

/** Фирменная роль для письменности, которую фирменная пара не покрывает: хвост рисует её. */
const brandWith = (tail: string, hosted: readonly string[]): FontDefinition =>
  role(`${BRAND_STACK}, ${tail}`, ["Onest", "Unbounded", ...hosted]);

const BRAND_LATIN = role(`${BRAND_STACK}, ${SYSTEM_STACK}`, ["Onest", "Unbounded"]);
const NATIVE_SYSTEM: FontDefinition = { stack: SYSTEM_STACK, hosted: [] };
const MONO_LATIN = role(
  '"JetBrains Mono", ui-monospace, "SFMono-Regular", Menlo, monospace',
  ["JetBrains Mono"],
);
const SANS_LATIN = role(`"Inter", ${SYSTEM_STACK}`, ["Inter"]);
const SERIF_LATIN = role('"Noto Serif", Georgia, "Times New Roman", serif', ["Noto Serif"]);

/** Латиница и кириллица: один набор на восемь языков; русский отличается засечками. */
const LATIN_SET: Readonly<Record<FontRole, FontDefinition>> = {
  whisperer: BRAND_LATIN,
  sans: SANS_LATIN,
  serif: SERIF_LATIN,
  native: NATIVE_SYSTEM,
  mono: MONO_LATIN,
};

export const FONT_CONFIG: Readonly<Record<FontLocale, Readonly<Record<FontRole, FontDefinition>>>> = {
  // У PT Serif кириллица — часть замысла, а не довесок к латинскому набору.
  ru: { ...LATIN_SET, serif: role('"PT Serif", Georgia, serif', ["PT Serif"]) },
  en: LATIN_SET,
  de: LATIN_SET,
  es: LATIN_SET,
  pt: LATIN_SET,
  fr: LATIN_SET,
  it: LATIN_SET,
  tr: LATIN_SET,

  id: { ...LATIN_SET, sans: role(`"Poppins", ${SYSTEM_STACK}`, ["Poppins"]) },

  // У Inter и Onest нет вьетнамских глифов ư ặ ị ọ ộ ờ ợ ứ ừ: запасной шрифт
  // мешал бы начертания внутри слова. Be Vietnam Pro сделан под язык.
  vi: {
    whisperer: brandWith(`"Be Vietnam Pro", ${SYSTEM_STACK}`, ["Be Vietnam Pro"]),
    sans: role(`"Be Vietnam Pro", ${SYSTEM_STACK}`, ["Be Vietnam Pro"]),
    serif: SERIF_LATIN,
    native: NATIVE_SYSTEM,
    mono: MONO_LATIN,
  },

  // Арабица: четыре разных начертания. Насх — «с засечками», куфи — native,
  // Kawkab Mono — единственный открытый моноширинный арабский.
  ar: {
    whisperer: brandWith('"Noto Sans Arabic", Tahoma, sans-serif', ["Noto Sans Arabic"]),
    sans: role('"Noto Sans Arabic", Tahoma, sans-serif', ["Noto Sans Arabic"]),
    serif: role('"Noto Naskh Arabic", "Times New Roman", serif', ["Noto Naskh Arabic"]),
    native: role('"Noto Kufi Arabic", Tahoma, sans-serif', ["Noto Kufi Arabic"]),
    mono: role(
      '"Kawkab Mono", "JetBrains Mono", ui-monospace, monospace',
      ["Kawkab Mono", "JetBrains Mono"],
    ),
  },

  // Моноширинного деванагари не существует: роль Mono моноширинная в латинице
  // и цифрах, а само письмо рисует Noto Sans Devanagari. Это предел письменности.
  hi: {
    whisperer: brandWith('"Noto Sans Devanagari", sans-serif', ["Noto Sans Devanagari"]),
    sans: role('"Hind", "Noto Sans Devanagari", sans-serif', ["Hind", "Noto Sans Devanagari"]),
    serif: role('"Noto Serif Devanagari", serif', ["Noto Serif Devanagari"]),
    native: role('"Noto Sans Devanagari", sans-serif', ["Noto Sans Devanagari"]),
    mono: role(
      '"JetBrains Mono", "Noto Sans Devanagari", ui-monospace, monospace',
      ["JetBrains Mono", "Noto Sans Devanagari"],
    ),
  },

  // Тайская: native — традиционное начертание «с петлями». Моноширинного
  // тайского тоже не существует.
  th: {
    whisperer: brandWith('"Noto Sans Thai", sans-serif', ["Noto Sans Thai"]),
    sans: role('"Noto Sans Thai", sans-serif', ["Noto Sans Thai"]),
    serif: role('"Noto Serif Thai", serif', ["Noto Serif Thai"]),
    native: role('"Noto Sans Thai Looped", "Noto Sans Thai", sans-serif', ["Noto Sans Thai Looped"]),
    mono: role(
      '"JetBrains Mono", "Noto Sans Thai", ui-monospace, monospace',
      ["JetBrains Mono", "Noto Sans Thai"],
    ),
  },

  // Японская, традиционная китайская, корейская: своё лицо у каждой роли,
  // включая моноширинную; у native системный шрифт и есть ответ.
  ja: {
    whisperer: brandWith('"Noto Sans JP", "Hiragino Sans", "Yu Gothic", sans-serif', ["Noto Sans JP"]),
    sans: role('"Noto Sans JP", "Hiragino Sans", "Yu Gothic", sans-serif', ["Noto Sans JP"]),
    serif: role('"Noto Serif JP", "Hiragino Mincho ProN", "Yu Mincho", serif', ["Noto Serif JP"]),
    native: { stack: '"Hiragino Sans", "Yu Gothic", "Noto Sans JP", sans-serif', hosted: [] },
    mono: role('"M PLUS 1 Code", "Noto Sans JP", ui-monospace, monospace', ["M PLUS 1 Code"]),
  },
  zh: {
    whisperer: brandWith(
      '"Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif',
      ["Noto Sans TC"],
    ),
    sans: role('"Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif', ["Noto Sans TC"]),
    serif: role('"Noto Serif TC", "Songti TC", "PMingLiU", serif', ["Noto Serif TC"]),
    native: { stack: '"PingFang TC", "Microsoft JhengHei", "Noto Sans TC", sans-serif', hosted: [] },
    mono: role(
      '"Noto Sans Mono CJK TC", "Noto Sans TC", ui-monospace, monospace',
      ["Noto Sans Mono CJK TC"],
    ),
  },
  ko: {
    whisperer: brandWith(
      '"Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif',
      ["Pretendard"],
    ),
    sans: role('"Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", sans-serif', ["Pretendard"]),
    serif: role('"Noto Serif KR", Batang, serif', ["Noto Serif KR"]),
    native: { stack: '"Apple SD Gothic Neo", "Malgun Gothic", "Pretendard", sans-serif', hosted: [] },
    mono: role('"D2Coding", "Pretendard", ui-monospace, monospace', ["D2Coding"]),
  },
};
