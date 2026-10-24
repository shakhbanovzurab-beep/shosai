import type { components } from "@/lib/api/generated/schema";

import type { LeoSource } from "./sources";
import type { LeoMessage, LeoMessageStatus, LeoStep } from "./types";

/* История треда из `/v1/agent/threads/{id}/messages` (docs/leo-api.md): страницы новыми вперёд, раунды модели скрыты. */

export type AgentThread = components["schemas"]["ThreadOut"];
export type AgentMessage = components["schemas"]["MessageOut"];
export type AgentPage<T> = { items: T[]; next_cursor: string | null };

const STATUS: Record<NonNullable<AgentMessage["status"]>, LeoMessageStatus> = {
  done: "done",
  stopped: "stopped",
  failed: "error",
};

function stepOf(step: AgentMessage["steps"][number]): LeoStep {
  return {
    id: step.id,
    action: step.activity,
    detail: step.detail ?? undefined,
    status: step.status === "failed" ? "error" : "done",
    durationMs: step.duration_ms ?? undefined,
  };
}

/** Сообщение панели из строки истории; заметка сервера читается как слова Leo. */
export function messageOf(row: AgentMessage): LeoMessage {
  const sources: LeoSource[] = row.sources.map(({ id, kind, title, space, locator, quote, highlight }) => ({
    id,
    kind,
    title,
    space,
    locator: locator ?? null,
    quote,
    highlight,
  }));
  return {
    id: row.id,
    role: row.role === "user" ? "user" : "assistant",
    content: row.text,
    status: row.status === null ? "done" : STATUS[row.status],
    steps: row.steps.map(stepOf),
    sources: sources.length > 0 ? sources : undefined,
    durationMs: row.duration_ms ?? undefined,
  };
}

/** Разговор старыми вперёд из страниц, пришедших новыми вперёд. */
export function conversationOf(pages: readonly AgentPage<AgentMessage>[]): LeoMessage[] {
  return pages
    .flatMap((page) => page.items)
    .toReversed()
    .map(messageOf);
}

/** Последний вопрос разговора: его можно задать заново или исправить. */
export function lastQuestion(messages: readonly LeoMessage[]): LeoMessage | undefined {
  return messages.findLast((message) => message.role === "user");
}
