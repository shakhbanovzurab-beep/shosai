import { MEMORY_KINDS, type MemoryFact, type MemoryKind } from "./contract";

/*
 * Загруженная страница в окне памяти: кандидаты отдельно сверху, факты — закреплённые первыми, затем новые, и
 * группы по видам. Вид и слова фильтрует сервер (`FactsQuery`), здесь — только раскладка.
 */

const newestFirst = (a: MemoryFact, b: MemoryFact) => b.created_at.localeCompare(a.created_at);

/** Кандидаты (новые сверху) и принятые факты (закреплённые, затем новые). */
export function splitFacts(facts: readonly MemoryFact[]) {
  const candidates = facts.filter((f) => f.status === "candidate").toSorted(newestFirst);
  const active = facts
    .filter((f) => f.status === "active")
    .toSorted((a, b) => Number(b.pinned) - Number(a.pinned) || newestFirst(a, b));
  return { candidates, active };
}

/** Группы по видам в постоянном порядке; пустые группы не показываются. */
export function groupByKind(facts: readonly MemoryFact[]): [MemoryKind, MemoryFact[]][] {
  return MEMORY_KINDS.map((kind): [MemoryKind, MemoryFact[]] => [kind, facts.filter((f) => f.kind === kind)]).filter(
    ([, group]) => group.length > 0,
  );
}
