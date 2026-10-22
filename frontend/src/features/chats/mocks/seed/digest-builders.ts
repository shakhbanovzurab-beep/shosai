import { LUMEN } from "@/features/workspace/mocks/demo-lumen";

import type { Binding, Messenger } from "../../domain/contract";
import type { ChatDigest, ChatMessageRef, DigestItem, DigestPromise } from "../../domain/digest-contract";
import { ago } from "./connections";

/* Строители дайджестов демо: сообщение, пункт, договорённость, пустой дайджест и его чат. */

const HOUR = 3_600_000;
const DAY = 24 * HOUR;
const inDays = (days: number) => new Date(Date.now() + days * DAY).toISOString().slice(0, 10);

export function message(
  url: string | null,
  n: number,
  author_name: string,
  hoursAgo: number,
  quote: string,
): ChatMessageRef {
  return { id: `msg-${n}`, author_name, sent_at: ago(hoursAgo * HOUR), quote, url: url ? `${url}/${n}` : null };
}

export const item = (id: string, text: string, ref: ChatMessageRef): DigestItem => ({
  id,
  text,
  message: ref,
  proposal_id: null,
  task_id: null,
});

export function promise(
  id: string,
  who: DigestPromise["who"],
  text: string,
  due: number | string | null,
  ref: ChatMessageRef,
) {
  const day = typeof due === "number" ? inDays(due) : null;
  return { ...item(id, text, ref), who, due_on: day, when_text: typeof due === "string" ? due : null };
}

/** Пункт, который Leo уже сделал задачей по просьбе в чате: она на доске (моки kanban, TK-D13). */
export const made = <T extends DigestItem>(value: T, taskId: string): T => ({ ...value, task_id: taskId });

export const TG = "https://t.me/c/2093847561";

/** Дайджест за дни `[fromDaysAgo, toDaysAgo]` без пунктов; пункты добавляет тот, кто его строит. */
export function digest(
  id: string,
  chat: ChatDigest["chat"],
  historyDaysAgo: number,
  read: number,
  days = [7, 0],
): ChatDigest {
  return {
    id,
    chat,
    period: { from: ago(days[0] * DAY), to: ago(days[1] * DAY) },
    created_at: ago(0),
    coverage: { history_from: ago(historyDaysAgo * DAY), messages_read: read, truncated: false },
    decisions: [],
    questions: [],
    promises: [],
  };
}

/** Чат дайджеста. Название — позиционно: его написали люди. */
export const chatRef = (id: string, messenger: Messenger, name: string, binding: Binding): ChatDigest["chat"] => ({
  id,
  workspace_id: LUMEN,
  messenger,
  title: name,
  binding,
});
