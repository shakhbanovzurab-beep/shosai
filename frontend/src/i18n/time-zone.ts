import { useSyncExternalStore } from "react";

/*
 * Часовой пояс кабинета: пояс из профиля (`GET /v1/me`, поле `timezone`), а без него — пояс браузера. В нём
 * печатаются все моменты и считаются календарные дни («сегодня», «вчера», «через 3 дня»). Значение, которое само
 * календарный день без времени (срок задачи, дата счёта, срок карты), печатается с `CALENDAR_DAY`: такой день
 * хранится полночью UTC и в UTC остаётся тем же днём в любом поясе (`calendar-days.ts`). См. docs/i18n.md.
 */

let browserZone: string | undefined;
let profileZone: string | null = null;
const listeners = new Set<() => void>();

/** Пояс браузера: его кабинет сохраняет в профиль при регистрации и в режиме «Автоматически». */
export function browserTimeZone(): string {
  browserZone ??= Intl.DateTimeFormat().resolvedOptions().timeZone;
  return browserZone;
}

// Пояс, которого не знает браузер (опечатка, устаревшее имя), не ломает форматирование: остаётся пояс браузера.
function knownZone(zone: string): boolean {
  try {
    new Intl.DateTimeFormat(undefined, { timeZone: zone });
    return true;
  } catch (error) {
    if (error instanceof RangeError) return false;
    throw error;
  }
}

/** Пояс из профиля; `null`, пустой или незнакомый браузеру — пояс браузера. */
export function setProfileTimeZone(zone: string | null | undefined): void {
  const next = zone && knownZone(zone) ? zone : null;
  if (next === profileZone) return;
  profileZone = next;
  for (const listener of listeners) listener();
}

/** Пояс кабинета сейчас — для кода вне React (моки, форматтеры модулей). */
export const cabinetTimeZone = (): string => profileZone ?? browserTimeZone();

/** Подписка на смену пояса кабинета — для хранилищ вне React, которые печатают время сами (часы в шапке). */
export const subscribeTimeZone = (listener: () => void) => {
  listeners.add(listener);
  return () => listeners.delete(listener);
};

/** Пояс кабинета для компонента: меняется, когда профиль назвал свой. */
export const useTimeZone = (): string => useSyncExternalStore(subscribeTimeZone, cabinetTimeZone, cabinetTimeZone);
