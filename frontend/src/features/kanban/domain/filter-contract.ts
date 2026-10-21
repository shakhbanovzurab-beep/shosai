import type { Priority } from "./tasks-contract";

/*
 * Фильтр доски (план пакета §4.5): поиск и по фильтру на каждое видимое поле. Выборы внутри поля — «или»,
 * поля и поиск вместе — «и». Живёт в адресе, а не хранится: ссылка воспроизводит вид.
 */

export const DUE_BUCKETS = ["overdue", "today", "week", "later", "none"] as const;
export type DueBucket = (typeof DUE_BUCKETS)[number];

/** Без исполнителя — отдельный выбор рядом с людьми доски. */
export const UNASSIGNED = "~unassigned";
/** Поле без значения — выбор рядом с состояниями набора. */
export const EMPTY_STATE = "~empty";

export type NumberFilter =
  | { mode: "empty" }
  | { mode: "set" }
  | { mode: "range"; from: number | null; to: number | null };

export type BoardFilter = {
  q: string;
  /** Ключ исполнителя: id участника пространства или имя у личной задачи; `UNASSIGNED` — без исполнителя. */
  assignee: string[];
  due: DueBucket[];
  priority: (Priority | "none")[];
  repeat: ("yes" | "no")[];
  states: Record<string, string[]>;
  numbers: Record<string, NumberFilter>;
  texts: Record<string, string>;
};

export const NO_FILTER: BoardFilter = {
  q: "",
  assignee: [],
  due: [],
  priority: [],
  repeat: [],
  states: {},
  numbers: {},
  texts: {},
};
