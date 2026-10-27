import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

import type { FactsPage, FactsQuery, FactUpdate, MemoryFact } from "../domain/contract";

/* Память Leo на `/v1/agent/memory*` (план memory §3.3): факты по страницам с фильтрами сервера и правки. */

const fact = (id: string) => ({ params: { path: { fact_id: id } } });

export const memoryApi = {
  list: (query: FactsQuery, cursor: string | null): Promise<FactsPage> =>
    dataOf(
      apiClient.GET("/v1/agent/memory", {
        params: { query: { kind: query.kind, q: query.words || null, cursor } },
      }),
    ),
  /** Новый текст требует ключа идемпотентности: повтор отвечает первым результатом, а не 404 на заменённый факт. */
  update: (id: string, body: FactUpdate, key: string): Promise<MemoryFact> =>
    dataOf(
      apiClient.PATCH("/v1/agent/memory/{fact_id}", {
        params: { path: { fact_id: id }, header: { "Idempotency-Key": key } },
        body,
      }),
    ),
  accept: (id: string): Promise<MemoryFact> => dataOf(apiClient.POST("/v1/agent/memory/{fact_id}/accept", fact(id))),
  forget: (id: string): Promise<void> => dataOf(apiClient.DELETE("/v1/agent/memory/{fact_id}", fact(id))),
  /** Вернуть забытый или заменённый в последние сутки факт. */
  restore: (id: string): Promise<MemoryFact> => dataOf(apiClient.POST("/v1/agent/memory/{fact_id}/restore", fact(id))),
  forgetAll: (): Promise<void> => dataOf(apiClient.DELETE("/v1/agent/memory")),
  /** Кандидаты беседы — для строки под ответом Leo. */
  threadCandidates: (threadId: string): Promise<FactsPage> =>
    dataOf(apiClient.GET("/v1/agent/memory", { params: { query: { thread_id: threadId, status: "candidate" } } })),
  /** Кандидаты, перенесённые из прежней памяти (MM-D8): только в своём списке. */
  imported: (cursor: string | null): Promise<FactsPage> =>
    dataOf(apiClient.GET("/v1/agent/memory", { params: { query: { source: "imported", cursor } } })),
  turnDownImported: (): Promise<void> => dataOf(apiClient.POST("/v1/agent/memory/imported/turn-down")),
  enabled: async (): Promise<boolean> => (await dataOf(apiClient.GET("/v1/agent/memory/settings"))).enabled,
  setEnabled: async (enabled: boolean): Promise<boolean> =>
    (await dataOf(apiClient.PATCH("/v1/agent/memory/settings", { body: { enabled } }))).enabled,
};
