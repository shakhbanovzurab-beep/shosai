import type { KanbanProblem } from "../../domain/problems";

/** Результат операции хранилища: значение или код отказа (ответ сервера строит маршрут). */
export type Outcome<T> = { ok: true; value: T } | { ok: false; code: KanbanProblem };
export const ok = <T>(value: T): Outcome<T> => ({ ok: true, value });
export const fail = (code: KanbanProblem): Outcome<never> => ({ ok: false, code });
