import type { components } from "@/lib/api/generated/schema";

import type { LeoProposal } from "./proposals";
import type { LeoSource } from "./sources";
import type { LeoMessage, LeoMessageStatus, LeoStep } from "./types";

/*
 * История треда из `/v1/agent/threads/{id}/messages` (docs/leo-api.md): страницы новыми вперёд, раунды модели
 * скрыты. Ответ несёт свои карточки в их нынешнем состоянии и артефакты. Заметка сервера говорит об итоге карточки:
 * карточка, которая уже стоит в своём ответе, второй раз не показывается — её итог виден на ней самой.
 */

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
export function messageOf(row: AgentMessage, shown: ReadonlySet<string> = new Set()): LeoMessage {
  const sources: LeoSource[] = row.sources.map(({ id, kind, title, space, locator, quote, highlight }) => ({
    id,
    kind,
    title,
    space,
    locator: locator ?? null,
    quote,
    highlight,
  }));
  const proposals: LeoProposal[] =
    row.role === "server" ? row.actions.filter((card) => !shown.has(card.id)) : row.actions;
  return {
    id: row.id,
    role: row.role === "user" ? "user" : "assistant",
    content: row.text,
    status: row.status === null ? "done" : STATUS[row.status],
    steps: row.steps.map(stepOf),
    sources: sources.length > 0 ? sources : undefined,
    proposals: proposals.length > 0 ? proposals : undefined,
    artifacts: row.artifacts.length > 0 ? row.artifacts : undefined,
    durationMs: row.duration_ms ?? undefined,
  };
}

/** Разговор старыми вперёд из страниц, пришедших новыми вперёд. */
export function conversationOf(pages: readonly AgentPage<AgentMessage>[]): LeoMessage[] {
  const rows = pages.flatMap((page) => page.items).toReversed();
  const shown = new Set(rows.flatMap((row) => (row.role === "server" ? [] : row.actions.map((card) => card.id))));
  return rows
    .filter((row) => row.role !== "server" || row.text !== "" || row.actions.some((card) => !shown.has(card.id)))
    .map((row) => messageOf(row, shown));
}

/** Последний вопрос разговора: его можно задать заново или исправить. */
export function lastQuestion(messages: readonly LeoMessage[]): LeoMessage | undefined {
  return messages.findLast((message) => message.role === "user");
}
