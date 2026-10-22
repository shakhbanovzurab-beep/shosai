import type { Stopwatch, TaskClocks, Timer, TimeTracking } from "../../domain/time-contract";
import { fail, type Outcome, ok } from "./outcome";
import { demo, placementOf, touchTask } from "./state";
import type { ClockSpan, StoredBoard, StoredTask } from "./types";

/*
 * Время задачи (ADR 0061): секундомер — отрезки по колонкам, таймер — момент конца или остаток на паузе, план и
 * факт — на задаче. Автоматизации секундомера доска применяет сама — при появлении задачи, переносе и выполнении.
 * Отрезок при переносе всегда закрывается в старой колонке, поэтому время по колонкам точное при любых переносах.
 */

const iso = (ms: number) => new Date(ms).toISOString();
const spansOf = (taskId: string) => demo().clocks.get(taskId) ?? [];
const openSpan = (spans: ClockSpan[]) => spans.find((span) => span.stopped_at === null) ?? null;

export function stopwatchOf(taskId: string): Stopwatch | null {
  const spans = spansOf(taskId);
  if (spans.length === 0) return null;
  let total_ms = 0;
  const by_column: Record<string, number> = {};
  for (const span of spans) {
    if (span.stopped_at === null) continue;
    const ms = span.stopped_at - span.started_at;
    total_ms += ms;
    if (span.column_id) by_column[span.column_id] = (by_column[span.column_id] ?? 0) + ms;
  }
  const open = openSpan(spans);
  return { running_since: open ? iso(open.started_at) : null, total_ms, by_column };
}

const trackingOf = (task: StoredTask): TimeTracking | null =>
  task.plan_minutes === null && task.fact_minutes === null
    ? null
    : { plan_minutes: task.plan_minutes, fact_minutes: task.fact_minutes };

export const clocksOf = (task: StoredTask): TaskClocks => ({
  stopwatch: stopwatchOf(task.id),
  timer: demo().timers.get(task.id) ?? null,
  time_tracking: trackingOf(task),
});

function startIn(taskId: string, columnId: string | null) {
  const spans = spansOf(taskId);
  if (openSpan(spans)) return;
  demo().clocks.set(taskId, [...spans, { column_id: columnId, started_at: Date.now(), stopped_at: null }]);
}

function stopOpen(taskId: string) {
  const open = openSpan(spansOf(taskId));
  if (open) open.stopped_at = Date.now();
  return open !== null;
}

/** Часы у задачи Jira не идут (KG-D8). */
const refusedFor = (task: StoredTask) => (task.jira ? fail("jira_unsupported") : null);

export function startStopwatch(task: StoredTask): Outcome<null> {
  const refusal = refusedFor(task);
  if (refusal) return refusal;
  startIn(task.id, placementOf(task.id)?.column.id ?? null);
  touchTask(task.id);
  return ok(null);
}

export function stopStopwatch(task: StoredTask): Outcome<null> {
  const refusal = refusedFor(task);
  if (refusal) return refusal;
  stopOpen(task.id);
  touchTask(task.id);
  return ok(null);
}

export function resetStopwatch(task: StoredTask): Outcome<null> {
  const refusal = refusedFor(task);
  if (refusal) return refusal;
  demo().clocks.delete(task.id);
  touchTask(task.id);
  return ok(null);
}

/** Задать таймер заново: отсчёт с этой минуты на всю длительность. */
export function setTimer(task: StoredTask, length_ms: number): Outcome<null> {
  const refusal = refusedFor(task);
  if (refusal) return refusal;
  demo().timers.set(task.id, { length_ms, ends_at: iso(Date.now() + length_ms), paused_left_ms: null });
  touchTask(task.id);
  return ok(null);
}

function held(timer: Timer, paused: boolean, now: number): Timer {
  if (paused && timer.ends_at) return { ...timer, ends_at: null, paused_left_ms: Date.parse(timer.ends_at) - now };
  if (!paused && timer.paused_left_ms !== null)
    return { ...timer, ends_at: iso(now + timer.paused_left_ms), paused_left_ms: null };
  return timer;
}

/** Пауза и продолжение; повтор ничего не меняет. После нуля остаток отрицательный — перерасход копится и дальше. */
export function holdTimer(task: StoredTask, paused: boolean): Outcome<null> {
  const refusal = refusedFor(task);
  if (refusal) return refusal;
  const timer = demo().timers.get(task.id);
  if (!timer) return fail("timer_not_set");
  demo().timers.set(task.id, held(timer, paused, Date.now()));
  touchTask(task.id);
  return ok(null);
}

export function clearTimer(task: StoredTask): Outcome<null> {
  const refusal = refusedFor(task);
  if (refusal) return refusal;
  demo().timers.delete(task.id);
  touchTask(task.id);
  return ok(null);
}

/** Автоматизации секундомера действуют, только пока доска его показывает; на доске Jira их нет. */
const automationsOf = (board: StoredBoard) => (board.jira || !board.system.stopwatch ? null : board.stopwatch);

/** Задача появилась на доске: создана на ней, пришла входящей или вернулась повтором. */
export function onArrival(board: StoredBoard, taskId: string, columnId: string) {
  const task = demo().tasks.get(taskId);
  if (automationsOf(board)?.start_on_arrival && task && task.status !== "done") startIn(taskId, columnId);
}

/** Задача перешла в другую колонку; новый статус уже записан. */
export function onMove(board: StoredBoard, taskId: string, from: string, to: string) {
  if (from === to) return;
  const automations = automationsOf(board);
  const done = demo().tasks.get(taskId)?.status === "done";
  const wasRunning = stopOpen(taskId);
  if (done && automations?.stop_on_done) return;
  if (wasRunning || (automations?.restart_on_move && !done)) startIn(taskId, to);
}

/** Задача выполнена: доска с этой автоматизацией останавливает её секундомер. */
export function onDone(taskId: string) {
  const board = placementOf(taskId)?.board;
  if (board && automationsOf(board)?.stop_on_done) stopOpen(taskId);
}
