/* Устройство веб-клиента для входа в звонок: его видит администратор LiveKit (атрибуты участника, A8). */

export type WebDevice = { os: string | null; os_version: string | null; client: "web"; browser: string | null };

const BROWSERS: [RegExp, string][] = [
  [/Edg\/(\d+)/, "Edge"],
  [/OPR\/(\d+)/, "Opera"],
  [/YaBrowser\/(\d+)/, "Yandex Browser"],
  [/Firefox\/(\d+)/, "Firefox"],
  [/Chrome\/(\d+)/, "Chrome"],
  [/Version\/(\d+).*Safari/, "Safari"],
];
const SYSTEMS: [RegExp, string][] = [
  [/iPhone|iPad/, "ios"],
  [/Android/, "android"],
  [/Mac OS X/, "macos"],
  [/Windows/, "windows"],
  [/Linux/, "linux"],
];

/** Браузер с главной версией и система по строке User-Agent; неизвестное — null. */
export function webDevice(userAgent: string): WebDevice {
  const browser = BROWSERS.map(([pattern, name]) => [userAgent.match(pattern), name] as const).find(([found]) => found);
  const os = SYSTEMS.find(([pattern]) => pattern.test(userAgent))?.[1] ?? null;
  return { os, os_version: null, client: "web", browser: browser ? `${browser[1]} ${browser[0]?.[1]}` : null };
}
