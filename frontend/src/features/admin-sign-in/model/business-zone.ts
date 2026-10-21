import { useSyncExternalStore } from "react";

import { dayIn } from "@/i18n/calendar-days";

/*
 * Деловой часовой пояс платформы (ADR 0058): в нём сервер считает сутки и месяцы итогов — расходы на ИИ, минуты,
 * токены, промокоды, — и админка показывает свои даты в нём же, с подписью «МСК». Это настройка платформы, не
 * браузера и не профиля: её называет сервер в ответе `GET /v1/admin/session`, который страж админки читает до
 * первой страницы. До ответа — пояс платформы по умолчанию.
 */

const PLATFORM_DEFAULT = "Europe/Moscow";
let zone = PLATFORM_DEFAULT;
const listeners = new Set<() => void>();

/** Пояс из ответа сервера; меняется, только если сервер назвал другой. */
export function setBusinessZone(next: string): void {
  if (next === zone) return;
  zone = next;
  for (const listener of listeners) listener();
}

/** Деловой пояс сейчас — для форматтеров вне React. */
export const businessZone = (): string => zone;

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

/** Деловой пояс для компонента. */
export const useBusinessZone = (): string => useSyncExternalStore(subscribe, businessZone, businessZone);

/** Подпись пояса рядом с датами: «МСК» для Москвы, иначе смещение от UTC, как его пишет Intl («GMT+1»). */
export function businessZoneLabel(name: string = zone): string {
  if (name === PLATFORM_DEFAULT) return "МСК";
  const parts = new Intl.DateTimeFormat("ru-RU", { timeZone: name, timeZoneName: "shortOffset" }).formatToParts(0);
  return parts.find((part) => part.type === "timeZoneName")?.value ?? name;
}

/** Сегодняшняя дата делового пояса, `YYYY-MM-DD`: по ней сервер судит, действует ли промокод. */
export const businessToday = (now: Date | number = Date.now()): string => dayIn(now, zone);
