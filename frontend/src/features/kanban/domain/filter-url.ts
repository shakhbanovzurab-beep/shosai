import { type BoardFilter, DUE_BUCKETS, type DueBucket, NO_FILTER, type NumberFilter } from "./filter-contract";
import { PRIORITIES, type Priority } from "./tasks-contract";

/*
 * Фильтр в адресе: повторяемые `assignee`, `due`, `priority`, `repeat`, а у своих полей — `state.<id>`
 * (повторяемый), `number.<id>` (`empty`, `set`, `range:<от>:<до>`), `text.<id>`. Прочие параметры адреса не
 * трогаются; неизвестные значения отбрасываются.
 */

const STATE = "state.";
const NUMBER = "number.";
const TEXT = "text.";
const OWN_KEYS = ["assignee", "due", "priority", "repeat"];

const isFilterKey = (key: string) =>
  OWN_KEYS.includes(key) || key.startsWith(STATE) || key.startsWith(NUMBER) || key.startsWith(TEXT);

function parseNumber(raw: string): NumberFilter | null {
  if (raw === "empty" || raw === "set") return { mode: raw };
  const [kind, from = "", to = ""] = raw.split(":");
  if (kind !== "range") return null;
  const bound = (text: string) => (text === "" || !Number.isFinite(Number(text)) ? null : Number(text));
  return { mode: "range", from: bound(from), to: bound(to) };
}

const numberParam = (filter: NumberFilter) =>
  filter.mode === "range" ? `range:${filter.from ?? ""}:${filter.to ?? ""}` : filter.mode;

const isPriority = (value: string): value is Priority | "none" =>
  value === "none" || (PRIORITIES as readonly string[]).includes(value);

export function filterFromSearch(params: URLSearchParams): BoardFilter {
  const filter: BoardFilter = {
    ...NO_FILTER,
    assignee: params.getAll("assignee").filter(Boolean),
    due: params.getAll("due").filter((value): value is DueBucket => (DUE_BUCKETS as readonly string[]).includes(value)),
    priority: params.getAll("priority").filter(isPriority),
    repeat: params.getAll("repeat").filter((value): value is "yes" | "no" => value === "yes" || value === "no"),
    states: {},
    numbers: {},
    texts: {},
  };
  for (const [key, value] of params) {
    if (key.startsWith(STATE) && value) {
      const id = key.slice(STATE.length);
      filter.states[id] = [...(filter.states[id] ?? []), value];
    }
    if (key.startsWith(NUMBER)) {
      const number = parseNumber(value);
      if (number) filter.numbers[key.slice(NUMBER.length)] = number;
    }
    if (key.startsWith(TEXT) && value.trim()) filter.texts[key.slice(TEXT.length)] = value;
  }
  return filter;
}

/** Адрес с этим фильтром: параметры фильтра заменяются, остальные (доска, открытая задача) остаются. */
export function searchWithFilter(base: URLSearchParams, filter: BoardFilter): URLSearchParams {
  const next = new URLSearchParams([...base].filter(([key]) => !isFilterKey(key)));
  for (const value of filter.assignee) next.append("assignee", value);
  for (const value of filter.due) next.append("due", value);
  for (const value of filter.priority) next.append("priority", value);
  for (const value of filter.repeat) next.append("repeat", value);
  for (const [id, chosen] of Object.entries(filter.states))
    for (const value of chosen) next.append(`${STATE}${id}`, value);
  for (const [id, number] of Object.entries(filter.numbers)) next.set(`${NUMBER}${id}`, numberParam(number));
  for (const [id, text] of Object.entries(filter.texts)) if (text.trim()) next.set(`${TEXT}${id}`, text);
  return next;
}
