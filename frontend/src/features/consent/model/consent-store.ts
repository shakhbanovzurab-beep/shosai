// Решение человека о cookie и запуск GTM в браузере (ADR 0047). Состояние модульное: кабинет — одно
// SPA в одной вкладке, а выбор общий для всех экранов; React читает его через useSyncExternalStore.
import { useSyncExternalStore } from "react";

import { readClientCookie, setClientCookie } from "@/lib/cookie.client";

import { startTagManager, type TagHost, updateTagConsent } from "../api/tag-manager";
import {
  CONSENT_COOKIE,
  CONSENT_DAYS,
  type ConsentChoice,
  containerIdFrom,
  decodeConsent,
  encodeConsent,
} from "../domain/consent";

const CONTAINER_ID = containerIdFrom(import.meta.env.VITE_GTM_CONTAINER_ID);
// Если браузер не простаивает, GTM всё равно стартует не позже чем через 2 с после первого кадра.
const IDLE_TIMEOUT_MS = 2000;

/** Есть ли что включать: без контейнера нет ни тегов, ни переключателя в настройках. */
export const tagManagerConfigured = CONTAINER_ID !== null;

const listeners = new Set<() => void>();
let decided: ConsentChoice | null | undefined;
let host: TagHost | null = null;
let scheduled = false;

function storedConsent(): ConsentChoice | null {
  if (decided === undefined) decided = decodeConsent(readClientCookie(CONSENT_COOKIE));
  return decided;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Выбор человека; null — ещё не решал. */
export function useConsent(): ConsentChoice | null {
  return useSyncExternalStore(subscribe, storedConsent, () => null);
}

/** Запоминает решение на полгода и сразу передаёт его GTM, если тот уже загружен. */
export function decideConsent(choice: ConsentChoice): void {
  setClientCookie(CONSENT_COOKIE, encodeConsent(choice), CONSENT_DAYS);
  decided = choice;
  if (host) updateTagConsent(host, choice);
  for (const listener of listeners) listener();
}

function browserTagHost(): TagHost {
  const page = window as Window & { dataLayer?: unknown[] };
  page.dataLayer ??= [];
  return {
    dataLayer: page.dataLayer,
    appendScript(src) {
      const script = document.createElement("script");
      script.async = true;
      script.src = src;
      document.head.append(script);
    },
  };
}

/** Запускает GTM после первого рендера, когда браузер простаивает: тег не задерживает интерфейс. */
export function startTagManagerWhenIdle(): void {
  const containerId = CONTAINER_ID;
  if (containerId === null || scheduled) return;
  scheduled = true;
  const start = () => {
    host = browserTagHost();
    startTagManager(host, containerId, storedConsent());
  };
  // В Safari requestIdleCallback может не быть: тогда сразу после текущей задачи.
  if (typeof (window as Partial<Window>).requestIdleCallback === "function")
    window.requestIdleCallback(start, { timeout: IDLE_TIMEOUT_MS });
  else setTimeout(start, 0);
}
