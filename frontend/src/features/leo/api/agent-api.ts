import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import { apiErrorOf } from "@/lib/api/errors";
import type { components } from "@/lib/api/generated/schema";

import type { AgentMessage, AgentPage, AgentThread } from "../domain/agent-history";
import type { LeoRating } from "../domain/types";

/*
 * Треды, история и ходы Leo — маршруты среза agent (docs/leo-api.md): человека — `/v1/agent/*` по его токену,
 * оператора платформы в админке — те же маршруты под `/v1/admin/agent/*` по cookie админа (AG-D5).
 */

export type AgentScope = components["schemas"]["ScopeIn"];
export type TurnBody = components["schemas"]["TurnBody"];

type RoutesBase = "/v1/agent" | "/v1/admin/agent";

const PAGE_SIZE = 50;

type StreamCall = Promise<{ data?: ReadableStream<Uint8Array> | null; error?: unknown; response: Response }>;

/** Поток событий хода, или ApiError отказа до потока (402, 403, 409, 429 …). */
async function streamOf(call: StreamCall): Promise<ReadableStream<Uint8Array>> {
  const { data, error, response } = await call;
  if (!response.ok || !data) throw apiErrorOf(response.status, error ?? null, response.headers);
  return data;
}

/** Разговор с Leo под одним префиксом маршрутов. */
function conversationRoutes(base: RoutesBase) {
  return {
    /** Последний тред пространства по активности, или null, пока в нём не спрашивали. */
    latestThread: async (scope: AgentScope): Promise<AgentThread | null> => {
      const query = { scope: scope.kind, workspace_id: scope.workspace_id ?? null, limit: 1 };
      const page = await dataOf(apiClient.GET(`${base}/threads`, { params: { query } }));
      return page.items[0] ?? null;
    },

    /** Треды пространства по активности, новыми вперёд: меню «Недавние чаты». */
    threads: (scope: AgentScope, cursor: string | null): Promise<AgentPage<AgentThread>> =>
      dataOf(
        apiClient.GET(`${base}/threads`, {
          params: { query: { scope: scope.kind, workspace_id: scope.workspace_id ?? null, cursor, limit: PAGE_SIZE } },
        }),
      ),

    rename: (threadId: string, title: string): Promise<AgentThread> =>
      dataOf(
        apiClient.PATCH(`${base}/threads/{thread_id}`, { params: { path: { thread_id: threadId } }, body: { title } }),
      ),

    /** Тред с его сообщениями; идущий в нём ход останавливается. */
    remove: async (threadId: string): Promise<void> => {
      await dataOf(apiClient.DELETE(`${base}/threads/{thread_id}`, { params: { path: { thread_id: threadId } } }));
    },

    /** Тред для первого вопроса; тот же ключ — тот же тред. */
    createThread: (scope: AgentScope, key: string): Promise<AgentThread> =>
      dataOf(apiClient.POST(`${base}/threads`, { body: { scope }, params: { header: { "Idempotency-Key": key } } })),

    messages: (threadId: string, cursor: string | null): Promise<AgentPage<AgentMessage>> =>
      dataOf(
        apiClient.GET(`${base}/threads/{thread_id}/messages`, {
          params: { path: { thread_id: threadId }, query: { cursor, limit: PAGE_SIZE } },
        }),
      ),

    /** Ход: тот же ключ — тот же прогон и его поток с первого события. */
    turn: (threadId: string, body: TurnBody, key: string, signal: AbortSignal) =>
      streamOf(
        apiClient.POST(`${base}/threads/{thread_id}/turns`, {
          params: { path: { thread_id: threadId }, header: { "Idempotency-Key": key } },
          body,
          parseAs: "stream",
          signal,
        }),
      ),

    /** Продолжение потока прогона после события `after`; 410 `run_events_gone` — журнал уже истёк. */
    resume: (runId: string, after: number, signal: AbortSignal) =>
      streamOf(
        apiClient.GET(`${base}/runs/{run_id}/events`, {
          params: { path: { run_id: runId }, header: { "Last-Event-ID": after } },
          parseAs: "stream",
          signal,
        }),
      ),

    cancel: async (runId: string): Promise<void> => {
      await dataOf(apiClient.POST(`${base}/runs/{run_id}/cancel`, { params: { path: { run_id: runId } } }));
    },
  };
}

/** Маршруты одного разговора с Leo: человека или оператора. */
export type AgentRoutes = ReturnType<typeof conversationRoutes>;

/** Оператор платформы в админке: его разговоры — данные платформы, без оценок, вложений и карточек. */
export const operatorRoutes: AgentRoutes = conversationRoutes("/v1/admin/agent");

export const agentApi = {
  ...conversationRoutes("/v1/agent"),

  /** Оценка ответа (AG-D13): `shared` — ход стал оценочным случаем с согласия человека. */
  rate: (messageId: string, rating: LeoRating): Promise<{ rating: LeoRating; shared: boolean }> =>
    dataOf(
      apiClient.PUT("/v1/agent/messages/{message_id}/feedback", {
        params: { path: { message_id: messageId } },
        body: { rating },
      }),
    ),

  /** Снять оценку; вместе с ней уходит и оценочный случай. */
  unrate: async (messageId: string): Promise<void> => {
    await dataOf(
      apiClient.DELETE("/v1/agent/messages/{message_id}/feedback", { params: { path: { message_id: messageId } } }),
    );
  },
};
