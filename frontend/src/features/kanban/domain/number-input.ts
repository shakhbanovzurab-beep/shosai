/*
 * Число, как его набирают на языках кабинета: цифры разных письменностей (арабские ٣, персидские ۳, деванагари ३,
 * полноширинные ３), разделители разрядов и дробной части — как принято в языке человека.
 */

/** Нули цифр, которые набирают люди кабинета: арабские, персидские, деванагари, бенгальские, полноширинные (CJK). */
const ZEROS = [0x0660, 0x06f0, 0x0966, 0x09e6, 0xff10];
const GROUP_SPACES = /^[\s\u00a0\u202f\u2009']$/;

/** Цифра другой письменности → 0–9; прочие знаки — как есть. */
function toAscii(text: string) {
  return [...text]
    .map((char) => {
      const code = char.codePointAt(0) ?? 0;
      const zero = ZEROS.find((start) => code >= start && code <= start + 9);
      return zero === undefined ? char : String(code - zero);
    })
    .join("");
}

/** Разделители разрядов и дробной части в языке человека («1,000.5» в английском, «1 000,5» в русском). */
function separatorsOf(locale: string) {
  const parts = new Intl.NumberFormat(locale).formatToParts(12_345.6);
  return {
    group: parts.find((part) => part.type === "group")?.value ?? ",",
    decimal: parts.find((part) => part.type === "decimal")?.value ?? ".",
  };
}

/** Без пробелов и разделителей разрядов; дробная часть — через точку. Знак за знаком, без регулярок из данных. */
function normalized(raw: string, locale: string) {
  const { group, decimal } = separatorsOf(locale);
  let text = "";
  for (const char of toAscii(raw.trim())) {
    if (char === group || char === "\u066c" || GROUP_SPACES.test(char)) continue;
    text += char === decimal || char === "\u066b" ? "." : char;
  }
  return text.replace(/^[\u2212\u2013]/, "-");
}

/** Набранное число на языке `locale` или null, если это не число. */
export function parseNumberInput(raw: string, locale: string): number | null {
  const text = normalized(raw, locale);
  if (!/^-?\d*\.?\d+$|^-?\d+\.$/.test(text)) return null;
  const number = Number(text);
  return Number.isFinite(number) ? number : null;
}
