// Построение переопределений ответов для состояний. Каждое — синтетика с
// причиной; тела, описанные в OpenAPI черновика, проверяет registry.test.ts.

import type { JsonValue } from "../fixtures/format.ts";
import type { Override } from "./types.ts";

/** Тело ответа 500 у черновика: generic_exception_handler (core/exceptions.py). */
const SERVER_ERROR_BODY: JsonValue = { error: { code: "internal_error", message: "Internal server error" } };

export function reply(method: string, path: string, status: number, body: JsonValue, reason: string): Override {
  return { method, path, respond: { status, body }, reason };
}

/** Запрос без ответа: экран остаётся в ожидании. */
export function hold(method: string, path: string): Override {
  return { method, path, respond: "hold", reason: "ответ не приходит: состояние ожидания" };
}

/** Сетевой сбой: запрос обрывается, ответа нет. */
export function networkFailure(method: string, path: string): Override {
  return { method, path, respond: "fail", reason: "соединение оборвалось: стенд записи сбоев сети не воспроизводит" };
}

/** Необработанная ошибка сервера черновика. */
export function serverError(method: string, path: string): Override {
  return reply(method, path, 500, SERVER_ERROR_BODY, "отказ сервера стенд записи не воспроизводит; тело — обработчик черновика");
}

/** Ответ FastAPI на непрошедшую валидацию тела (HTTPValidationError). */
export function validationError(method: string, path: string, field: string): Override {
  return reply(
    method,
    path,
    422,
    { detail: [{ type: "missing", loc: ["body", field], msg: "Field required", input: null }] },
    "ошибку валидации стенд записи не получает: фронтенд шлёт полные тела",
  );
}

/**
 * Обновление токена у гостя: на любой 401 фронтенд пробует обновить сессию,
 * которой нет. Ответ — api/auth.py черновика без cookie обновления.
 */
export function guestRefresh(): Override {
  return reply("POST", "/v1/auth/refresh", 401, { detail: "Missing refresh cookie" }, "у гостя нет сессии: 401 на вход через соцсеть запускает попытку обновить токен");
}

/** Событие потока SSE: имя и данные, как их шлёт черновик. */
export interface StreamEvent {
  readonly event: string;
  readonly data: JsonValue;
}

/**
 * Законченный поток событий (SSE) одним ответом. Поток, который ещё идёт, —
 * `openStream`: ответ, отданный Playwright, всегда заканчивается.
 */
export function stream(method: string, path: string, events: readonly StreamEvent[], reason: string): Override {
  return { method, path, respond: { status: 200, body: streamBody(events), contentType: "text/event-stream" }, reason };
}

/**
 * Поток, который ещё идёт: события уже пришли, соединение открыто, конца нет.
 * Экран застывает в «ответ печатается».
 */
export function openStream(method: string, path: string, events: readonly StreamEvent[], reason: string): Override {
  return { method, path, respond: { open: streamBody(events) }, reason };
}

/** Кадры SSE: именованные события или безымянные `data:` (событие ""). */
export function streamBody(events: readonly StreamEvent[]): string {
  return events
    .map(({ event, data }) => {
      const payload = typeof data === "string" ? data : JSON.stringify(data);
      return event === "" ? `data: ${payload}\n\n` : `event: ${event}\ndata: ${payload}\n\n`;
    })
    .join("");
}

/** Перебор частоты: тело обработчика slowapi черновика. Лимиты на стенде записи выключены. */
export function rateLimited(method: string, path: string, limit: string): Override {
  return reply(method, path, 429, { error: `Rate limit exceeded: ${limit}` }, "лимиты на стенде записи выключены; тело — обработчик slowapi черновика");
}
