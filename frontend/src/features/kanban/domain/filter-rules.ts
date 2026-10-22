import { type BoardFilter, type DueBucket, EMPTY_STATE, type NumberFilter, UNASSIGNED } from "./filter-contract";
import { daysFrom } from "./recurrence";
import type { Assignee, Card } from "./tasks-contract";

/* Совпадает ли карточка с фильтром доски (план пакета §4.5). */

export const assigneeKey = (assignee: Assignee | null) =>
  assignee === null ? UNASSIGNED : (assignee.user_id ?? assignee.name);

/** Срок карточки по отношению к сегодняшнему дню человека; закрытая задача просроченной не бывает. */
export function dueBucket(card: Pick<Card, "due_on" | "status">, today: string): DueBucket | null {
  if (card.due_on === null) return "none";
  const days = daysFrom(today, card.due_on);
  if (days < 0) return card.status === "done" ? null : "overdue";
  if (days === 0) return "today";
  return days < 7 ? "week" : "later";
}

const fold = (text: string) => text.toLocaleLowerCase().normalize("NFKC");
/** Есть ли в тексте этот кусок (оба уже приведены `fold`). */
const contains = (text: string, part: string) => text.includes(part);

function numberMatches(filter: NumberFilter, value: number | undefined) {
  if (filter.mode === "empty") return value === undefined;
  if (value === undefined) return false;
  if (filter.mode === "set") return true;
  return (filter.from === null || value >= filter.from) && (filter.to === null || value <= filter.to);
}

function textOf(card: Card, stickerId: string) {
  const value = card.values[stickerId];
  return value && "text" in value ? value.text : "";
}

function stickersMatch(card: Card, filter: BoardFilter) {
  for (const [id, chosen] of Object.entries(filter.states)) {
    const value = card.values[id];
    const state = value && "state_id" in value ? value.state_id : EMPTY_STATE;
    if (chosen.length > 0 && !chosen.includes(state)) return false;
  }
  for (const [id, number] of Object.entries(filter.numbers)) {
    const value = card.values[id];
    if (!numberMatches(number, value && "number" in value ? value.number : undefined)) return false;
  }
  for (const [id, text] of Object.entries(filter.texts))
    if (text.trim() && !contains(fold(textOf(card, id)), fold(text.trim()))) return false;
  return true;
}

export function cardMatches(card: Card, filter: BoardFilter, today: string): boolean {
  if (filter.assignee.length > 0 && !filter.assignee.includes(assigneeKey(card.assignee))) return false;
  if (filter.due.length > 0) {
    const bucket = dueBucket(card, today);
    if (bucket === null || !filter.due.includes(bucket)) return false;
  }
  if (filter.priority.length > 0 && !filter.priority.includes(card.priority ?? "none")) return false;
  if (filter.repeat.length > 0 && !filter.repeat.includes(card.recurring ? "yes" : "no")) return false;
  return stickersMatch(card, filter);
}

/** Фильтр, который что-то отсеивает. */
export function isFiltering(filter: BoardFilter) {
  return (
    filter.assignee.length + filter.due.length + filter.priority.length + filter.repeat.length > 0 ||
    Object.values(filter.states).some((chosen) => chosen.length > 0) ||
    Object.keys(filter.numbers).length > 0 ||
    Object.values(filter.texts).some((text) => text.trim() !== "")
  );
}

/** Фильтр только по полям, видимым на доске: скрытое поле теряет и свой фильтр. */
export function forVisible(filter: BoardFilter, visible: ReadonlySet<string>): BoardFilter {
  const keep = <T>(record: Record<string, T>) =>
    Object.fromEntries(Object.entries(record).filter(([id]) => visible.has(id)));
  return {
    ...filter,
    assignee: visible.has("assignee") ? filter.assignee : [],
    due: visible.has("due") ? filter.due : [],
    priority: visible.has("priority") ? filter.priority : [],
    repeat: visible.has("recurrence") ? filter.repeat : [],
    states: keep(filter.states),
    numbers: keep(filter.numbers),
    texts: keep(filter.texts),
  };
}
