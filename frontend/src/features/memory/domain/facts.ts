import { MEMORY_KINDS, type MemoryFact, type MemoryKind } from "./contract";

/*
 * Список фактов на странице памяти: кандидаты отдельно сверху, остальные — закреплённые первыми, затем новые;
 * фильтр по виду и поиск по тексту.
 */

export type KindFilter = MemoryKind | "all";

const newestFirst = (a: MemoryFact, b: MemoryFact) => b.created_at.localeCompare(a.created_at);

/** Кандидаты (новые сверху) и принятые факты (закреплённые, затем новые). */
export function splitFacts(facts: readonly MemoryFact[]) {
  const candidates = facts.filter((f) => f.status === "candidate").toSorted(newestFirst);
  const active = facts
    .filter((f) => f.status === "active")
    .toSorted((a, b) => Number(b.pinned) - Number(a.pinned) || newestFirst(a, b));
  return { candidates, active };
}

/** Сколько принятых фактов каждого вида — для подписей фильтра. */
export function countByKind(active: readonly MemoryFact[]): Record<MemoryKind, number> {
  const counts = Object.fromEntries(MEMORY_KINDS.map((kind) => [kind, 0])) as Record<MemoryKind, number>;
  for (const fact of active) counts[fact.kind] += 1;
  return counts;
}

/** Факты выбранного вида, в тексте которых есть запрос (без учёта регистра в языке интерфейса). */
export function filterFacts(active: readonly MemoryFact[], kind: KindFilter, query: string, locale: string) {
  const needle = query.trim().toLocaleLowerCase(locale);
  return active.filter(
    (fact) =>
      (kind === "all" || fact.kind === kind) &&
      (needle === "" || fact.statement.toLocaleLowerCase(locale).includes(needle)),
  );
}

/** Группы по видам в постоянном порядке; пустые группы не показываются. */
export function groupByKind(facts: readonly MemoryFact[]): [MemoryKind, MemoryFact[]][] {
  return MEMORY_KINDS.map((kind): [MemoryKind, MemoryFact[]] => [kind, facts.filter((f) => f.kind === kind)]).filter(
    ([, group]) => group.length > 0,
  );
}
