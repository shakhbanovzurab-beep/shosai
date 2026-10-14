import type { components } from "@/lib/api/generated/schema";

/** Человек, вошедший в кабинет: профиль, согласия и роли оператора из `GET /v1/me`. */
export type Me = components["schemas"]["Me"];

/** Ответ входа и обновления: токен доступа живёт только в памяти, refresh — в httpOnly cookie. */
export type Tokens = components["schemas"]["TokenResponse"];

/** Сессия вкладки: ещё не знаем, вошёл человек или нет; вошёл; вышел. */
export type SessionStatus = "unknown" | "signed-in" | "signed-out";

/** Cookie с CSRF-значением сессии: его читает кабинет и отправляет в `X-CSRF-Token` (identity §3.7). */
export const CSRF_COOKIE = "meetassist_csrf";
