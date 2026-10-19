"use client";

import { useMemo } from "react";

import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { apiErrorDescription } from "@/lib/api/error-description";

import { memoryApi } from "../api/memory-api";
import type { MemoryFact } from "../domain/contract";
import { changeFacts } from "./facts-resource";

/*
 * Действия со страницы памяти. Список меняется сразу; если сервер откажет, правка откатывается и тост говорит
 * почему. «Забыть» с отменой — в `pending-forget.ts`.
 */

export type MemoryWords = {
  t: ReturnType<typeof useTranslations<"memory">>;
  common: ReturnType<typeof useTranslations<"common">>;
};

export function useMemoryWords(): MemoryWords {
  const t = useTranslations("memory");
  const common = useTranslations("common");
  return useMemo(() => ({ t, common }), [t, common]);
}

const replace = (id: string, next: MemoryFact) => changeFacts((facts) => facts.map((f) => (f.id === id ? next : f)));
const without = (id: string) => changeFacts((facts) => facts.filter((f) => f.id !== id));
const restore = (fact: MemoryFact) => changeFacts((facts) => [...facts.filter((f) => f.id !== fact.id), fact]);

function failed(error: unknown, title: string) {
  toast.error(title, { description: apiErrorDescription(error) });
}

/** «Запомнить»: кандидат становится фактом, который Leo использует. */
export async function acceptFact(fact: MemoryFact, { t }: MemoryWords) {
  replace(fact.id, { ...fact, status: "active" });
  try {
    replace(fact.id, await memoryApi.accept(fact.id));
  } catch (error) {
    replace(fact.id, fact);
    failed(error, t("failed.save"));
  }
}

/** «Не запоминать»: кандидат уходит, Leo его не использует. */
export async function rejectFact(fact: MemoryFact, { t }: MemoryWords) {
  without(fact.id);
  try {
    await memoryApi.forget(fact.id);
  } catch (error) {
    restore(fact);
    failed(error, t("failed.save"));
  }
}

export async function setPinned(fact: MemoryFact, pinned: boolean, { t }: MemoryWords) {
  replace(fact.id, { ...fact, pinned });
  try {
    replace(fact.id, await memoryApi.update(fact.id, { pinned }));
  } catch (error) {
    replace(fact.id, fact);
    failed(error, t("failed.save"));
  }
}

/** Новый текст заменяет факт (supersession): у ответа новый id. true — сохранено. */
export async function editFact(fact: MemoryFact, statement: string, { t }: MemoryWords): Promise<boolean> {
  try {
    replace(fact.id, await memoryApi.update(fact.id, { statement }));
    return true;
  } catch (error) {
    failed(error, t("failed.save"));
    return false;
  }
}

/** Правка из редактора: флаг занятости держится, пока идёт запрос, и снимается в любом исходе. */
export async function saveFactEdit(
  fact: MemoryFact,
  statement: string,
  words: MemoryWords,
  setBusy: (busy: boolean) => void,
): Promise<boolean> {
  setBusy(true);
  try {
    return await editFact(fact, statement, words);
  } finally {
    setBusy(false);
  }
}

/** «Забыть всё» — после подтверждения в диалоге; отмены нет. */
export async function forgetAll({ t }: MemoryWords) {
  try {
    await memoryApi.forgetAll();
    changeFacts(() => []);
    toast.success(t("forgetAll.done"));
  } catch (error) {
    failed(error, t("failed.forget"));
  }
}
