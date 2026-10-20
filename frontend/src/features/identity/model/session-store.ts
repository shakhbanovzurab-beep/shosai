import { useSyncExternalStore } from "react";

import { setProfileTimeZone } from "@/i18n/time-zone";

import type { Me, SessionStatus } from "../domain/session";

export interface SessionState {
  status: SessionStatus;
  // Токен доступа — только в памяти вкладки, никогда в хранилище браузера (identity §3.7).
  accessToken: string | null;
  me: Me | null;
}

const SIGNED_OUT: SessionState = { status: "signed-out", accessToken: null, me: null };
let state: SessionState = { status: "unknown", accessToken: null, me: null };
const listeners = new Set<() => void>();

export function sessionState(): SessionState {
  return state;
}

export function updateSession(change: Partial<SessionState>): void {
  state = { ...state, ...change };
  // Пояс профиля — пояс всего кабинета; без профиля (выход) снова пояс браузера.
  if ("me" in change) setProfileTimeZone(change.me?.timezone);
  for (const listener of listeners) listener();
}

export function clearSession(): void {
  updateSession(SIGNED_OUT);
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Сессия этой вкладки; меняется, когда другая вкладка обновила токен или вышла. */
export function useSession(): SessionState {
  return useSyncExternalStore(subscribe, sessionState, sessionState);
}

/** Вошедший человек или null, пока сессия не загружена. */
export function useMe(): Me | null {
  return useSession().me;
}
