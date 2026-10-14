import { ApiError } from "@/lib/api/errors";
import { readClientCookie } from "@/lib/cookie.client";

import { endSession, readMe, refreshSession } from "../api/session-api";
import { CSRF_COOKIE, type Me } from "../domain/session";
import { clearSession, sessionState, updateSession } from "./session-store";
import { exclusively, listenToTabs, tellTabs } from "./session-tabs";

let renewing: Promise<string | null> | null = null;
let started: Promise<Me | null> | null = null;

/** Токен доступа вкладки для заголовка Authorization. */
export function accessToken(): string | null {
  return sessionState().accessToken;
}

/**
 * Токен новее `failed`: если его уже обновили — этой или другой вкладкой, — он и возвращается; иначе одно
 * обновление на всю вкладку под замком браузера. null — сессия кончилась: refresh отвергнут сервером.
 * Сетевая ошибка и 5xx пробрасываются: они не значат, что человек вышел.
 */
export function renewSession(failed: string | null): Promise<string | null> {
  const current = accessToken();
  if (current !== null && current !== failed) return Promise.resolve(current);
  renewing ??= exclusively(async () => {
    const latest = accessToken();
    if (latest !== null && latest !== failed) return latest;
    return refreshNow();
  }).finally(() => {
    renewing = null;
  });
  return renewing;
}

// Без refresh-cookie сервер ответит 401 сам: решать, вошёл ли человек, — его дело, не вкладки.
async function refreshNow(): Promise<string | null> {
  try {
    const tokens = await refreshSession(readClientCookie(CSRF_COOKIE));
    adoptToken(tokens.access_token, true);
    return tokens.access_token;
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 403)) return signedOut(true);
    throw error;
  }
}

function adoptToken(token: string, broadcast: boolean): void {
  updateSession({ status: "signed-in", accessToken: token });
  if (broadcast) tellTabs({ kind: "token", token });
}

function signedOut(broadcast: boolean): null {
  started = Promise.resolve(null);
  clearSession();
  if (broadcast) tellTabs({ kind: "signed-out" });
  return null;
}

/** Загрузить вошедшего человека заново: после входа, смены профиля или языка. */
export async function loadMe(): Promise<Me> {
  const me = await readMe();
  updateSession({ me });
  return me;
}

/**
 * Сессия вкладки при запуске: обновление по refresh-cookie, затем профиль. Один промис на вкладку — его ждут
 * охрана маршрутов и экран входа; запускается из main.tsx, параллельно с каталогом языка и кодом страницы.
 */
export function startSession(): Promise<Me | null> {
  listenToTabs((message) => (message.kind === "token" ? adoptToken(message.token, false) : signedOut(false)));
  // Провал сети или сервера не запоминается: следующая навигация пробует снова.
  started ??= renewSession(null)
    .then((token) => (token === null ? null : loadMe()))
    .catch((error: unknown) => {
      started = null;
      throw error;
    });
  return started;
}

/** Принять токен входа этой вкладки, загрузить профиль и сообщить остальным вкладкам. */
export async function signedIn(token: string): Promise<Me> {
  adoptToken(token, true);
  const me = loadMe();
  started = me;
  return me;
}

/** Выйти на этом устройстве: сервер закрывает сессию, все вкладки забывают токен. */
export async function signOut(): Promise<void> {
  try {
    await endSession(readClientCookie(CSRF_COOKIE));
  } finally {
    signedOut(true);
  }
}
