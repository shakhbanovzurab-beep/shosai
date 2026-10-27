import type { components } from "@/lib/api/generated/schema";

/*
 * Сводка памяти и поле «Спросить или обновить» (ADR 0071 MM-D3) — `/v1/agent/memory/summary*` бэкенда `memory`.
 * Сводку пишет модель по текущим фактам; чтение модели не зовёт. Сообщение отвечает на вопрос или меняет факты,
 * и каждое изменение отменяется.
 */

type Schemas = components["schemas"];

/** Разделы, до трёх вопросов, когда написана и устарела ли: факты изменились, и переписывание уже в пути. */
export type MemorySummary = Schemas["MemorySummaryOut"];

/** Ответ на сообщение: ответ на вопрос, изменения фактов и сводка после них. */
export type MemoryMessageReply = Schemas["MemoryMessageOut"];

/** Изменение факта: `remembered`, `updated` (с `replaced_id` — что заменено) или `forgotten`. */
export type MemoryChange = Schemas["MemoryChangeOut"];

export const SUMMARY_MESSAGE_MAX = 2000;
