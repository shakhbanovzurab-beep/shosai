import type { components } from "@/lib/api/generated/schema";

/*
 * Время задачи (пакет Kanban time, ADR 0061; дополнение TK-D12, план tasks §3.8): секундомер — часы самой задачи
 * с временем по колонкам, таймер — обратный отсчёт заданной человеком длительности, план и факт. Время — сервера:
 * идущие часы — это момент начала, экран считает от `server_now` ответа.
 */

type Schemas = components["schemas"];

/** Секундомер: закрытые отрезки (всего и по колонкам) и момент начала идущего, если он идёт. */
export type Stopwatch = Schemas["StopwatchOut"];

/** Таймер: идёт, пока задан `ends_at`; на паузе — `paused_left_ms` (после нуля — отрицательный, это перерасход). */
export type Timer = Schemas["TimerOut"];

/** План и факт в минутах; null — не задано. */
export type TimeTracking = Schemas["TimeTrackingOut"];

/** Три поля времени на задаче; каждое null, пока им не пользовались. */
export type TaskClocks = Pick<Schemas["Card"], "stopwatch" | "timer" | "time_tracking">;

/** Ответ действий с часами: поля времени и момент ответа сервера. */
export type ClocksReply = Schemas["ClocksReply"];

/** Автоматизации секундомера на доске (KT-D2): при появлении задачи, при переносе, при выполнении. */
export type StopwatchAutomations = Schemas["AutomationsOut"];

/** Как в референсе: доска, включившая секундомер, перезапускает его по колонкам и останавливает на выполненной. */
export const DEFAULT_STOPWATCH_AUTOMATIONS: StopwatchAutomations = {
  start_on_arrival: false,
  restart_on_move: true,
  stop_on_done: true,
};

export type TimerSet = Schemas["TimerBody"];

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
