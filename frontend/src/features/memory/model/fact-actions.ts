"use client";

import { useMemo } from "react";

import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { apiErrorDescription } from "@/lib/api/error-description";

import { memoryApi } from "../api/memory-api";
import type { MemoryFact } from "../domain/contract";
import { changeFacts, clearFacts, count } from "./facts-resource";

/*
 * Действия в окне памяти. Список меняется сразу; если сервер откажет, правка откатывается и тост говорит почему.
 * «Забыть» с отменой — в `pending-forget.ts`.
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

export function failed(error: unknown, title: string) {
  toast.error(title, { description: apiErrorDescription(error) });
}

/** «Запомнить»: кандидат становится фактом, который Leo использует. */
export async function acceptFact(fact: MemoryFact, { t }: MemoryWords) {
  replace(fact.id, { ...fact, status: "active" });
  count(1, -1);
  try {
    replace(fact.id, await memoryApi.accept(fact.id));
  } catch (error) {
    replace(fact.id, fact);
    count(-1, 1);
    failed(error, t("failed.save"));
  }
}

/** «Не запоминать»: кандидат уходит, Leo его не использует. */
export async function rejectFact(fact: MemoryFact, { t }: MemoryWords) {
  without(fact.id);
  count(0, -1);
  try {
    await memoryApi.forget(fact.id);
  } catch (error) {
    restore(fact);
    count(0, 1);
    failed(error, t("failed.save"));
  }
}

export async function setPinned(fact: MemoryFact, pinned: boolean, { t }: MemoryWords) {
  replace(fact.id, { ...fact, pinned });
  try {
    replace(fact.id, await memoryApi.update(fact.id, { pinned }, crypto.randomUUID()));
  } catch (error) {
    replace(fact.id, fact);
    failed(error, t("failed.save"));
  }
}

/**
 * Правка из редактора: новый текст заменяет факт, у ответа новый id. Ключ один на правку, флаг занятости держится,
 * пока идёт запрос. true — сохранено.
 */
export async function saveFactEdit(
  fact: MemoryFact,
  statement: string,
  { t }: MemoryWords,
  setBusy: (busy: boolean) => void,
): Promise<boolean> {
  setBusy(true);
  try {
    replace(fact.id, await memoryApi.update(fact.id, { statement }, crypto.randomUUID()));
    return true;
  } catch (error) {
    failed(error, t("failed.save"));
    return false;
  } finally {
    setBusy(false);
  }
}

/** «Забыть всё» — после подтверждения в диалоге; отмены нет. */
export async function forgetAll({ t }: MemoryWords) {
  try {
    await memoryApi.forgetAll();
    clearFacts();
    toast.success(t("forgetAll.done"));
  } catch (error) {
    failed(error, t("failed.forget"));
  }
}
