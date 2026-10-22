import type { StopwatchBucket, TimerBucket, TrackingBucket } from "./filter-contract";
import type { Card } from "./tasks-contract";
import type { Stopwatch, TaskClocks, Timer, TimeTracking } from "./time-contract";

/*
 * Что показывают часы задачи в момент `now` (мс эпохи по серверу): сами часы — это моменты, а не счётчики. Здесь же —
 * как действие с часами выглядит сразу, до ответа сервера, и суммы колонок.
 */

const iso = (ms: number) => new Date(ms).toISOString();

/** Сколько всего на секундомере: закрытые отрезки и идущий. */
export const stopwatchElapsed = (stopwatch: Stopwatch, now: number) =>
  stopwatch.total_ms + (stopwatch.running_since ? Math.max(0, now - Date.parse(stopwatch.running_since)) : 0);

/** Сколько идёт нынешний отрезок; 0 — секундомер стоит. */
export const runningSpan = (stopwatch: Stopwatch | null, now: number) =>
  stopwatch?.running_since ? Math.max(0, now - Date.parse(stopwatch.running_since)) : 0;

/** Сколько осталось таймеру; меньше нуля — перерасход. На паузе время стоит. */
export const timerLeft = (timer: Timer, now: number) =>
  timer.ends_at ? Date.parse(timer.ends_at) - now : (timer.paused_left_ms ?? 0);

/** Факт сверх плана. */
export const overPlan = ({ plan_minutes: plan, fact_minutes: fact }: TimeTracking) =>
  plan !== null && fact !== null && fact > plan;

/* Корзины фильтров (KT-D7). */

export function stopwatchBucket(stopwatch: Stopwatch | null): StopwatchBucket {
  if (stopwatch === null) return "none";
  return stopwatch.running_since ? "running" : "stopped";
}

export function timerBucket(timer: Timer | null, now: number): TimerBucket {
  if (timer === null) return "none";
  return timerLeft(timer, now) > 0 ? "left" : "up";
}

export function trackingBucket(tracking: TimeTracking | null): TrackingBucket {
  if (!tracking || tracking.plan_minutes === null) return "none";
  return overPlan(tracking) ? "over" : "within";
}

/* Как действие выглядит сразу; ответ сервера потом встаёт на его место. */

export const started = (stopwatch: Stopwatch | null, now: number): Stopwatch =>
  stopwatch?.running_since
    ? stopwatch
    : { running_since: iso(now), total_ms: stopwatch?.total_ms ?? 0, by_column: stopwatch?.by_column ?? {} };

/** Остановить; идущий отрезок ложится в колонку, где задача сейчас. */
export function stopped(stopwatch: Stopwatch | null, now: number, columnId: string | null): Stopwatch | null {
  if (!stopwatch?.running_since) return stopwatch;
  const span = runningSpan(stopwatch, now);
  const by_column = { ...stopwatch.by_column };
  if (columnId) by_column[columnId] = (by_column[columnId] ?? 0) + span;
  return { running_since: null, total_ms: stopwatch.total_ms + span, by_column };
}

export const timerFrom = (length_ms: number, now: number): Timer => ({
  length_ms,
  ends_at: iso(now + length_ms),
  paused_left_ms: null,
});

/** Пауза или продолжение; повтор ничего не меняет. */
export function held(timer: Timer | null, paused: boolean, now: number): Timer | null {
  if (!timer) return timer;
  if (paused && timer.ends_at) return { ...timer, ends_at: null, paused_left_ms: timerLeft(timer, now) };
  if (!paused && timer.paused_left_ms !== null)
    return { ...timer, ends_at: iso(now + timer.paused_left_ms), paused_left_ms: null };
  return timer;
}

/** План и факт после правки; оба пустые — учёта нет. */
export function trackingWith(tracking: TimeTracking | null, patch: Partial<TimeTracking>): TimeTracking | null {
  const next = { plan_minutes: null, fact_minutes: null, ...tracking, ...patch };
  return next.plan_minutes === null && next.fact_minutes === null ? null : next;
}

export const clocksOf = ({ stopwatch, timer, time_tracking }: TaskClocks): TaskClocks => ({
  stopwatch,
  timer,
  time_tracking,
});

/* Суммы колонки по карточкам, которые она показывает. */

/** Время карточек в этой колонке: закрытые отрезки в ней и идущий (задача идёт там, где стоит). */
export function columnTime(ids: string[], cards: Record<string, Card>, columnId: string, now: number) {
  let total = 0;
  let found = false;
  for (const id of ids) {
    const stopwatch = cards[id]?.stopwatch;
    if (!stopwatch) continue;
    total += (stopwatch.by_column[columnId] ?? 0) + runningSpan(stopwatch, now);
    found = true;
  }
  return found ? total : null;
}

/** Σ плана и Σ факта в минутах; null — ни у одной карточки нет учёта. */
export function trackingSums(ids: string[], cards: Record<string, Card>) {
  let plan = 0;
  let fact = 0;
  let found = false;
  for (const id of ids) {
    const tracking = cards[id]?.time_tracking;
    if (!tracking) continue;
    plan += tracking.plan_minutes ?? 0;
    fact += tracking.fact_minutes ?? 0;
    found = true;
  }
  return found ? { plan, fact } : null;
}
