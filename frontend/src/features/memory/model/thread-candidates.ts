"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";

import { memoryApi } from "../api/memory-api";
import type { MemoryFact } from "../domain/contract";
import { failed } from "./fact-actions";
import { factsResource } from "./facts-resource";

/*
 * Кандидаты беседы для строки под ответом Leo (MM-D1): читаются под последним ответом, когда беседа открыта или
 * ответ закончился, и ещё раз через несколько секунд — столько память разбирает ход в фоне. Уведомлений нет.
 */

const ADMISSION_MS = 8_000;

const candidatesKey = (threadId: string, answerId: string) =>
  ["memory", "thread-candidates", threadId, answerId] as const;

// Первое чтение — сразу, второе — когда память успела разобрать ход; дальше строка не опрашивает.
const READS = 2;

export function useThreadCandidates(threadId: string, answerId: string): MemoryFact[] {
  const query = useQuery({
    queryKey: candidatesKey(threadId, answerId),
    queryFn: async () => (await memoryApi.threadCandidates(threadId)).items,
    staleTime: Number.POSITIVE_INFINITY,
    refetchInterval: (state) => (state.state.dataUpdateCount < READS ? ADMISSION_MS : false),
  });
  return query.data ?? [];
}

/** Ответ на кандидата из строки: он уходит из строки сразу; отказ сервера возвращает его и говорит почему. */
export function useAnswerCandidate(threadId: string, answerId: string) {
  const client = useQueryClient();
  const key = candidatesKey(threadId, answerId);
  return async (fact: MemoryFact, remember: boolean, failedTitle: string) => {
    client.setQueryData<MemoryFact[]>(key, (facts) => facts?.filter((f) => f.id !== fact.id));
    try {
      if (remember) await memoryApi.accept(fact.id);
      else await memoryApi.forget(fact.id);
      void factsResource.reload();
    } catch (error) {
      failed(error, failedTitle);
      void client.invalidateQueries({ queryKey: key });
    }
  };
}
