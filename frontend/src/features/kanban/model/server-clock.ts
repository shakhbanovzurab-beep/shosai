"use client";

import { useSyncExternalStore } from "react";

/*
 * Часы по серверу (KT-D6): расхождение часов устройства с сервером запоминается из `server_now` каждого ответа,
 * а один такт на минуту будит все карточки с идущими часами, сколько бы их ни было на досках. Пока ни одна
 * карточка не слушает, таймера нет вовсе.
 */

const MINUTE_MS = 60_000;

let skewMs = 0;
let timer: ReturnType<typeof setTimeout> | undefined;
const listeners = new Set<() => void>();

const notify = () => {
  for (const listener of listeners) listener();
};

/** Сейчас по часам сервера, в мс эпохи. */
export const serverTime = () => Date.now() + skewMs;

/** Ответ сервера с `server_now`: часы, которые уже идут на экране, сразу встают по нему. */
export function noteServerNow(serverNow: string) {
  const at = Date.parse(serverNow);
  if (!Number.isFinite(at)) return;
  const next = at - Date.now();
  // Разница в секунды — задержка сети, а не сбитые часы: минуты на карточках от неё не меняются.
  if (Math.abs(next - skewMs) < 1000) return;
  skewMs = next;
  // Такт встаёт на границу минуты по новым часам.
  if (listeners.size > 0) {
    clearTimeout(timer);
    schedule();
  }
  notify();
}

function schedule() {
  timer = setTimeout(
    () => {
      notify();
      schedule();
    },
    MINUTE_MS - (serverTime() % MINUTE_MS),
  );
}

/** Слушать такт минуты; возвращает отписку. */
export function subscribeMinute(listener: () => void) {
  listeners.add(listener);
  if (listeners.size === 1) schedule();
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0) clearTimeout(timer);
  };
}

const minute = () => Math.floor(serverTime() / MINUTE_MS) * MINUTE_MS;

/** Сейчас по серверу с точностью до минуты; перерисовывает только того, кто спросил, раз в минуту. */
export const useServerMinute = () => useSyncExternalStore(subscribeMinute, minute, minute);
