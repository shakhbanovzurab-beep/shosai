import type { ChatsProblem } from "../../domain/problems";

/** Результат операции хранилища: значение или код отказа с параметрами (ответ сервера строит маршрут). */
export type Outcome<T> =
  | { ok: true; value: T }
  | { ok: false; code: ChatsProblem; params?: Record<string, string | number | string[]> };
export const ok = <T>(value: T): Outcome<T> => ({ ok: true, value });
export const fail = (code: ChatsProblem, params?: Record<string, string | number | string[]>): Outcome<never> => ({
  ok: false,
  code,
  params,
});
