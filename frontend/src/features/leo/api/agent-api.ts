import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import { apiErrorOf } from "@/lib/api/errors";
import type { components } from "@/lib/api/generated/schema";

import type { AgentMessage, AgentPage, AgentThread } from "../domain/agent-history";

/* Треды, история и ходы Leo — маршруты среза agent (`/v1/agent/*`, docs/leo-api.md). */

export type AgentScope = components["schemas"]["ScopeIn"];
export type TurnBody = components["schemas"]["TurnBody"];

const PAGE_SIZE = 50;

type StreamCall = Promise<{ data?: ReadableStream<Uint8Array> | null; error?: unknown; response: Response }>;

/** Поток событий хода, или ApiError отказа до потока (402, 403, 409, 429 …). */
async function streamOf(call: StreamCall): Promise<ReadableStream<Uint8Array>> {
  const { data, error, response } = await call;
  if (!response.ok || !data) throw apiErrorOf(response.status, error ?? null, response.headers);
  return data;
}

export const agentApi = {
  /** Последний тред пространства по активности, или null, пока в нём не спрашивали. */
  latestThread: async (scope: AgentScope): Promise<AgentThread | null> => {
    const query = { scope: scope.kind, workspace_id: scope.workspace_id ?? null, limit: 1 };
    const page = await dataOf(apiClient.GET("/v1/agent/threads", { params: { query } }));
    return page.items[0] ?? null;
  },

  /** Тред для первого вопроса; тот же ключ — тот же тред. */
  createThread: (scope: AgentScope, key: string): Promise<AgentThread> =>
    dataOf(apiClient.POST("/v1/agent/threads", { body: { scope }, params: { header: { "Idempotency-Key": key } } })),

  messages: (threadId: string, cursor: string | null): Promise<AgentPage<AgentMessage>> =>
    dataOf(
      apiClient.GET("/v1/agent/threads/{thread_id}/messages", {
        params: { path: { thread_id: threadId }, query: { cursor, limit: PAGE_SIZE } },
      }),
    ),

  /** Ход: тот же ключ — тот же прогон и его поток с первого события. */
  turn: (threadId: string, body: TurnBody, key: string, signal: AbortSignal) =>
    streamOf(
      apiClient.POST("/v1/agent/threads/{thread_id}/turns", {
        params: { path: { thread_id: threadId }, header: { "Idempotency-Key": key } },
        body,
        parseAs: "stream",
        signal,
      }),
    ),

  /** Продолжение потока прогона после события `after`; 410 `run_events_gone` — журнал уже истёк. */
  resume: (runId: string, after: number, signal: AbortSignal) =>
    streamOf(
      apiClient.GET("/v1/agent/runs/{run_id}/events", {
        params: { path: { run_id: runId }, header: { "Last-Event-ID": after } },
        parseAs: "stream",
        signal,
      }),
    ),

  cancel: async (runId: string): Promise<void> => {
    await dataOf(apiClient.POST("/v1/agent/runs/{run_id}/cancel", { params: { path: { run_id: runId } } }));
  },
};
