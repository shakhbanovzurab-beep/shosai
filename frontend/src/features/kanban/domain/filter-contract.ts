import type { Priority } from "./tasks-contract";

/*
 * Фильтр доски (план пакета §4.5): по фильтру на каждое видимое поле. Выборы внутри поля — «или», поля вместе — «и».
 * Живёт в адресе, а не хранится: ссылка воспроизводит вид. Своего поиска у доски нет — задачи ищет глобальный
 * поиск кабинета (решение владельца 2026-10-22).
 */

export const DUE_BUCKETS = ["overdue", "today", "week", "later", "none"] as const;
export type DueBucket = (typeof DUE_BUCKETS)[number];

/** Поля времени (KT-D7): секундомер идёт, стоит или не запускался; у таймера есть время, вышло или его нет;
 * факт сверх плана, в плане или плана нет. */
export const STOPWATCH_BUCKETS = ["running", "stopped", "none"] as const;
export const TIMER_BUCKETS = ["left", "up", "none"] as const;
export const TRACKING_BUCKETS = ["over", "within", "none"] as const;
export type StopwatchBucket = (typeof STOPWATCH_BUCKETS)[number];
export type TimerBucket = (typeof TIMER_BUCKETS)[number];
export type TrackingBucket = (typeof TRACKING_BUCKETS)[number];

/** Без исполнителя — отдельный выбор рядом с людьми доски. */
export const UNASSIGNED = "~unassigned";
/** Поле без значения — выбор рядом с состояниями набора. */
export const EMPTY_STATE = "~empty";

export type NumberFilter =
  | { mode: "empty" }
  | { mode: "set" }
  | { mode: "range"; from: number | null; to: number | null };

export type BoardFilter = {
  /** Ключ исполнителя: id участника пространства или имя у личной задачи; `UNASSIGNED` — без исполнителя. */
  assignee: string[];
  due: DueBucket[];
  priority: (Priority | "none")[];
  repeat: ("yes" | "no")[];
  stopwatch: StopwatchBucket[];
  timer: TimerBucket[];
  tracking: TrackingBucket[];
  states: Record<string, string[]>;
  numbers: Record<string, NumberFilter>;
  texts: Record<string, string>;
};

export const NO_FILTER: BoardFilter = {
  assignee: [],
  due: [],
  priority: [],
  repeat: [],
  stopwatch: [],
  timer: [],
  tracking: [],
  states: {},
  numbers: {},
  texts: {},
};
