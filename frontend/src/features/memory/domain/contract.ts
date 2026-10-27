import type { components } from "@/lib/api/generated/schema";

/*
 * Что помнит Leo о человеке (ADR 0071, Leo §7.2) — маршруты `/v1/agent/memory*` бэкенда `memory` (план memory §3.3),
 * типы из его OpenAPI. Подробно — docs/memory-api.md.
 */

type Schemas = components["schemas"];

/** Предпочтение, факт о человеке, люди, цели, как человек работает. */
export const MEMORY_KINDS = ["preference", "fact", "relationship", "goal", "procedure"] as const;
export type MemoryKind = Schemas["FactKind"];

/** Откуда факт: чат с Leo, встреча, командный чат, настройки, правка человека, прежняя память. */
export type SourceKind = Schemas["MemorySource"];

/** Факт или кандидат; `statement` — данные человека, показываются как написаны (`dir="auto"`). */
export type MemoryFact = Schemas["MemoryFactOut"];

/** Страница фактов: кандидаты первыми, потом факты, новые сверху; счётчики — по всей памяти. */
export type FactsPage = Schemas["FactsPageOut"];
export type MemoryCounts = Schemas["MemoryCountsOut"];

/** Новый текст (заменяет факт: у ответа новый id) или закрепление. */
export type FactUpdate = Schemas["FactPatch"];

/** Что выбрано в окне памяти: вид и слова; фильтрует сервер, поэтому они покрывают все страницы. */
export type FactsQuery = { kind: MemoryKind | null; words: string };

export const STATEMENT_MAX = 500;
export const WORDS_MAX = 200;
