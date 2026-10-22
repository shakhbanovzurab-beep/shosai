/*
 * Время задачи (пакет Kanban time, ADR 0061; дополнение TK-D12, план tasks §3.8): секундомер — часы самой задачи
 * с временем по колонкам, таймер — обратный отсчёт заданной человеком длительности, план и факт. Время — сервера:
 * идущие часы — это момент начала, экран считает от `server_now` ответа.
 */

/** Секундомер: закрытые отрезки (всего и по колонкам) и момент начала идущего, если он идёт. */
export type Stopwatch = {
  running_since: string | null;
  total_ms: number;
  by_column: Record<string, number>;
};

/** Таймер: идёт, пока задан `ends_at`; на паузе — `paused_left_ms` (после нуля — отрицательный, это перерасход). */
export type Timer = { length_ms: number; ends_at: string | null; paused_left_ms: number | null };

/** План и факт в минутах; null — не задано. */
export type TimeTracking = { plan_minutes: number | null; fact_minutes: number | null };

/** Три поля времени на задаче; каждое null, пока им не пользовались. */
export type TaskClocks = {
  stopwatch: Stopwatch | null;
  timer: Timer | null;
  time_tracking: TimeTracking | null;
};

/** Ответ действий с часами: поля времени и момент ответа сервера. */
export type ClocksReply = TaskClocks & { server_now: string };

/** Автоматизации секундомера на доске (KT-D2). */
export type StopwatchAutomations = {
  /** Запускать, когда задача появляется на доске: создана на ней или пришла с другой. */
  start_on_arrival: boolean;
  /** Перезапускать при переносе между колонками и показывать сумму по колонке. */
  restart_on_move: boolean;
  /** Останавливать, когда задача выполнена. */
  stop_on_done: boolean;
};

/** Как в референсе: доска, включившая секундомер, перезапускает его по колонкам и останавливает на выполненной. */
export const DEFAULT_STOPWATCH_AUTOMATIONS: StopwatchAutomations = {
  start_on_arrival: false,
  restart_on_move: true,
  stop_on_done: true,
};

export type TimerSet = { length_ms: number };

const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;

/** Готовые длительности таймера (KT-D3): 30 минут, час, 4 часа, день, неделя. */
export const TIMER_PRESETS_MS = [30 * MINUTE_MS, HOUR_MS, 4 * HOUR_MS, DAY_MS, 7 * DAY_MS] as const;
/** Своя длительность — от минуты до года. */
export const TIMER_MIN_MS = MINUTE_MS;
export const TIMER_MAX_MS = 365 * DAY_MS;
/** План и факт — до 100 000 часов. */
export const TRACKED_MINUTES_MAX = 6_000_000;
