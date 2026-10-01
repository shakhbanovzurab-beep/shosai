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
