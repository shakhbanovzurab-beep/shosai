import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

import type { MemoryMessageReply, MemorySummary } from "../domain/summary-contract";

/* Сводка памяти на `/v1/agent/memory/summary*` (план memory §3.3, MM-D3). */

export const summaryApi = {
  /** Последняя сводка; модель не зовётся, устаревшая переписывается в фоне. */
  get: (): Promise<MemorySummary> => dataOf(apiClient.GET("/v1/agent/memory/summary")),
  /** Переписать сейчас: не чаще десяти раз в час. */
  refresh: (): Promise<MemorySummary> => dataOf(apiClient.POST("/v1/agent/memory/summary/refresh")),
  /** Вопрос или изменение; ключ один на сообщение — повтор отвечает первым результатом. */
  send: (message: string, key: string): Promise<MemoryMessageReply> =>
    dataOf(
      apiClient.POST("/v1/agent/memory/summary/messages", {
        params: { header: { "Idempotency-Key": key } },
        body: { message },
      }),
    ),
};
