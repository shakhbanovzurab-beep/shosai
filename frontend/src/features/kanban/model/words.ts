import type { ReactNode } from "react";

import type { useTranslations } from "use-intl";

import { apiErrorDescription } from "@/lib/api/error-description";

import { kanbanProblemOf } from "../domain/problems";

/*
 * Каталоги, которыми действия модели называют свои тосты. Действия — обычные функции, поэтому клиентский
 * компонент, который их вызывает, передаёт свои переводчики (`useTranslations("kanban")` и другие).
 */

export type KanbanWords = ReturnType<typeof useTranslations<"kanban">>;
export type BoardWords = ReturnType<typeof useTranslations<"kanbanBoards">>;
export type CommonWords = ReturnType<typeof useTranslations<"common">>;
export type ApiWords = ReturnType<typeof useTranslations<"kanbanApi">>;

/** Отказ, как его читает человек: известный код — словами кабинета, иначе текст сервера и id запроса. */
export function describeProblem(error: unknown, ta: ApiWords): ReactNode {
  const code = kanbanProblemOf(error);
  return code === null ? apiErrorDescription(error) : ta(code);
}
