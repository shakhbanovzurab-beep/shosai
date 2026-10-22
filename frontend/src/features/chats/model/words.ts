import type { ReactNode } from "react";

import type { useTranslations } from "use-intl";

import { apiErrorDescription } from "@/lib/api/error-description";

import { chatsProblemOf } from "../domain/problems";

/*
 * Каталоги, которыми действия модели называют свои тосты. Действия — обычные функции, поэтому компонент,
 * который их вызывает, передаёт свои переводчики.
 */

export type ChatsWords = ReturnType<typeof useTranslations<"chats">>;
export type ConnectWords = ReturnType<typeof useTranslations<"chatsConnect">>;
export type ApiWords = ReturnType<typeof useTranslations<"chatsApi">>;

/** Отказ, как его читает человек: известный код — словами кабинета, иначе текст сервера и id запроса. */
export function describeProblem(error: unknown, ta: ApiWords): ReactNode {
  const code = chatsProblemOf(error);
  return code === null ? apiErrorDescription(error) : ta(code);
}
