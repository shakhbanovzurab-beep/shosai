import type { Stopwatch, Timer, TimeTracking } from "./time-contract";

/* Что показывают часы задачи в момент `now` (мс эпохи по серверу): сами часы — это моменты, а не счётчики. */

/** Сколько всего на секундомере: закрытые отрезки и идущий. */
export const stopwatchElapsed = (stopwatch: Stopwatch, now: number) =>
  stopwatch.total_ms + (stopwatch.running_since ? Math.max(0, now - Date.parse(stopwatch.running_since)) : 0);

/** Сколько осталось таймеру; меньше нуля — перерасход. На паузе время стоит. */
export const timerLeft = (timer: Timer, now: number) =>
  timer.ends_at ? Date.parse(timer.ends_at) - now : (timer.paused_left_ms ?? 0);

/** Факт сверх плана. */
export const overPlan = ({ plan_minutes: plan, fact_minutes: fact }: TimeTracking) =>
  plan !== null && fact !== null && fact > plan;
