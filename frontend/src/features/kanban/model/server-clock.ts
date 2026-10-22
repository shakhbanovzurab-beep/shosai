"use client";

import { useSyncExternalStore } from "react";

/*
 * Часы по серверу (KT-D6): расхождение часов устройства с сервером запоминается из `server_now` каждого ответа.
 * Один такт на минуту будит все карточки с идущими часами, сколько бы их ни было на досках; такт на секунду — только
 * открытую панель. Пока такт никто не слушает, его таймера нет вовсе.
 */

let skewMs = 0;

/** Сейчас по часам сервера, в мс эпохи. */
export const serverTime = () => Date.now() + skewMs;

/** Такт с шагом `periodMs` по часам сервера: один таймер на всех слушателей. */
function ticker(periodMs: number) {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const listeners = new Set<() => void>();
  const notify = () => {
    for (const listener of listeners) listener();
  };
  const schedule = () => {
    timer = setTimeout(
      () => {
        notify();
        schedule();
      },
      periodMs - (serverTime() % periodMs),
    );
  };
  return {
    subscribe(listener: () => void) {
      listeners.add(listener);
      if (listeners.size === 1) schedule();
      return () => {
        listeners.delete(listener);
        if (listeners.size === 0) clearTimeout(timer);
      };
    },
    snapshot: () => Math.floor(serverTime() / periodMs) * periodMs,
    /** Часы сдвинулись: такт встаёт на границу по новым часам, слушатели перечитывают время. */
    realign() {
      if (listeners.size === 0) return;
      clearTimeout(timer);
      schedule();
      notify();
    },
  };
}

const minutes = ticker(60_000);
const seconds = ticker(1000);

/** Ответ сервера с `server_now`: часы, которые уже идут на экране, сразу встают по нему. */
export function noteServerNow(serverNow: string) {
  const at = Date.parse(serverNow);
  if (!Number.isFinite(at)) return;
  const next = at - Date.now();
  // Разница меньше секунды — задержка сети, а не сбитые часы.
  if (Math.abs(next - skewMs) < 1000) return;
  skewMs = next;
  minutes.realign();
  seconds.realign();
}

/** Нынешняя минута по серверу — для обработчиков событий, вне отрисовки. */
export const serverMinute = minutes.snapshot;

/** Слушать такт минуты; возвращает отписку. */
export const subscribeMinute = minutes.subscribe;

/** Сейчас по серверу с точностью до минуты; перерисовывает только того, кто спросил, раз в минуту. */
export const useServerMinute = () => useSyncExternalStore(minutes.subscribe, minutes.snapshot, minutes.snapshot);

/** Сейчас по серверу с точностью до секунды — для часов открытой панели. */
export const useServerSecond = () => useSyncExternalStore(seconds.subscribe, seconds.snapshot, seconds.snapshot);

const idle = () => () => {};
const zero = () => 0;

/** Минута по серверу, только пока она нужна (`active`); иначе 0 и никакого такта. */
export const useServerMinuteWhile = (active: boolean) =>
  useSyncExternalStore(active ? minutes.subscribe : idle, active ? minutes.snapshot : zero, zero);

/** Секунда по серверу, только пока часы идут (`active`); иначе 0 и никакого такта. */
export const useServerSecondWhile = (active: boolean) =>
  useSyncExternalStore(active ? seconds.subscribe : idle, active ? seconds.snapshot : zero, zero);
