import type { Middleware } from "openapi-fetch";

/**
 * Что промежуточному обработчику нужно от сессии: текущий токен доступа и способ получить новый. Сессию
 * реализует слайс identity; здесь только механика заголовка и повтора, без знания о входе.
 */
export interface SessionPort {
  accessToken(): string | null;
  /** Токен новее `failed`, обновлённый один раз на все вызовы и вкладки; null — сессия закончилась. */
  renew(failed: string | null): Promise<string | null>;
}

// Маршруты, которые сами открывают или закрывают сессию: их 401 — ответ, а не истёкший токен, и обновлять сессию
// ради них нечего. Остальные пути /v1/auth (код для десктоп-приложения) требуют входа, как любой другой.
const SIGN_IN_PATH = /^\/v1\/auth\/(login|refresh|logout|register|password|social|desktop\/(exchange|refresh))(\/|$)/;
// Админка входит своей cookie (ADR 0049): токен человека ей не нужен, а её 401 — не истёкший токен.
const ADMIN_PATH = /^\/v1\/admin(\/|$)/;

interface SentRequest {
  replay: Request;
  token: string | null;
}

function outsidePersonSession(request: Request): boolean {
  const path = new URL(request.url).pathname;
  return SIGN_IN_PATH.test(path) || ADMIN_PATH.test(path);
}

/**
 * Ставит `Authorization: Bearer` и на 401 один раз обновляет токен и повторяет запрос (identity §3.7).
 * Обновление общее для параллельных запросов: порт отдаёт новый токен всем, кто прислал прежний.
 * 5xx, 429 и сетевые ошибки проходят как есть — они не значат, что сессия кончилась.
 */
export function sessionMiddleware(port: SessionPort): Middleware {
  const sent = new Map<string, SentRequest>();
  return {
    onRequest({ request, id }) {
      if (outsidePersonSession(request)) return request;
      const token = port.accessToken();
      if (token !== null && !request.headers.has("authorization")) {
        request.headers.set("authorization", `Bearer ${token}`);
      }
      sent.set(id, { replay: request.clone(), token });
      return request;
    },
    async onResponse({ response, id }) {
      const original = sent.get(id);
      sent.delete(id);
      if (original === undefined || response.status !== 401) return response;
      const token = await port.renew(original.token);
      if (token === null) return response;
      const replay = new Request(original.replay);
      replay.headers.set("authorization", `Bearer ${token}`);
      return fetch(replay);
    },
    onError({ id }) {
      sent.delete(id);
    },
  };
}
