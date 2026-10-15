/**
 * Понятное название устройства из строки клиента, которую сервер хранит как подпись сессии: «Chrome · macOS»,
 * «Shosai · Windows». Названия браузеров и систем — собственные имена, они не переводятся. Неузнанная строка —
 * null, и интерфейс пишет общее «Браузер» или «Приложение для компьютера».
 */

// Порядок важен: Edge, Opera и Яндекс.Браузер называют себя ещё и Chrome, Chrome — ещё и Safari.
const BROWSERS: readonly (readonly [RegExp, string])[] = [
  [/\bShosai\//, "Shosai"],
  [/\bWhisperer\//, "Shosai"],
  [/\bEdg(e|A|iOS)?\//, "Edge"],
  [/\bOPR\/|\bOpera\b/, "Opera"],
  [/\bYaBrowser\//, "Yandex Browser"],
  [/\bFirefox\/|\bFxiOS\//, "Firefox"],
  [/Chrome\/|\bCriOS\//, "Chrome"],
  [/\bSafari\//, "Safari"],
];

const SYSTEMS: readonly (readonly [RegExp, string])[] = [
  [/\biPhone\b|\biPad\b|\biOS\b/, "iOS"],
  [/\bAndroid\b/, "Android"],
  [/\bMac OS X\b|\bMacintosh\b|\bmacOS\b/, "macOS"],
  [/\bWindows\b/, "Windows"],
  [/\bCrOS\b/, "ChromeOS"],
  [/\bLinux\b/, "Linux"],
];

const firstMatch = (label: string, table: readonly (readonly [RegExp, string])[]) =>
  table.find(([pattern]) => pattern.test(label))?.[1] ?? null;

export function deviceName(label: string | null): string | null {
  if (!label) return null;
  const browser = firstMatch(label, BROWSERS);
  const system = firstMatch(label, SYSTEMS);
  if (browser && system) return `${browser} · ${system}`;
  return browser ?? system;
}
