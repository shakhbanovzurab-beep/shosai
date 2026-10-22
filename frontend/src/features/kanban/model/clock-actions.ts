"use client";

import { clocksApi } from "../api/clocks-api";
import { tasksApi } from "../api/tasks-api";
import type { TaskDetail } from "../domain/tasks-contract";
import { type ClocksReply, type TaskClocks, type TimeTracking, TRACKED_MINUTES_MAX } from "../domain/time-contract";
import { clocksOf, held, runningSpan, started, stopped, timerFrom, trackingWith } from "../domain/time-rules";
import type { BoardStore } from "./board-store";
import { noteServerNow, serverTime } from "./server-clock";
import { changeTask, freshTask, type TaskWords } from "./task-sync";

/*
 * Часы задачи из панели (ADR 0061): видны сразу и в панели, и на карточке; ответ сервера встаёт на место
 * предсказанного, отказ возвращает только то поле, которое менялось.
 */

type Predict = (detail: TaskDetail, now: number) => Partial<TaskClocks>;

const pick = (detail: TaskDetail, keys: (keyof TaskClocks)[]): Partial<TaskClocks> =>
  Object.fromEntries(keys.map((key) => [key, detail[key]]));

export function clockActions(id: string, store: BoardStore | null, words: TaskWords) {
  function changeClocks(predict: Predict, request: () => Promise<ClocksReply>) {
    let before: Partial<TaskClocks> = {};
    return changeTask(id, store, words, {
      apply: (detail) => {
        const next = predict(detail, serverTime());
        before = pick(detail, Object.keys(next) as (keyof TaskClocks)[]);
        return { ...detail, ...next };
      },
      revert: (detail) => ({ ...detail, ...before }),
      work: async () => {
        const reply = await request();
        noteServerNow(reply.server_now);
        const clocks = clocksOf(reply);
        return (detail) => ({ ...detail, ...clocks });
      },
    });
  }

  function changeTracking(next: (tracking: TimeTracking | null) => Partial<TimeTracking>) {
    let before: TimeTracking | null = null;
    let patch: Partial<TimeTracking> = {};
    return changeTask(id, store, words, {
      apply: (detail) => {
        before = detail.time_tracking;
        patch = next(before);
        return { ...detail, time_tracking: trackingWith(before, patch) };
      },
      revert: (detail) => ({ ...detail, time_tracking: before }),
      work: async () => freshTask(await tasksApi.patch(id, patch)),
    });
  }

  return {
    start: () =>
      changeClocks(
        (d, now) => ({ stopwatch: started(d.stopwatch, now) }),
        () => clocksApi.stopwatch(id, "start"),
      ),
    /** Остановить; отвечает длиной остановленного отрезка (мс) или null, если сервер отказал. */
    async stop() {
      let span = 0;
      const done = await changeClocks(
        (d, now) => {
          span = runningSpan(d.stopwatch, now);
          return { stopwatch: stopped(d.stopwatch, now, d.placement?.column_id ?? null) };
        },
        () => clocksApi.stopwatch(id, "stop"),
      );
      return done ? span : null;
    },
    reset: () =>
      changeClocks(
        () => ({ stopwatch: null }),
        () => clocksApi.stopwatch(id, "reset"),
      ),
    setTimer: (length_ms: number) =>
      changeClocks(
        (_, now) => ({ timer: timerFrom(length_ms, now) }),
        () => clocksApi.setTimer(id, { length_ms }),
      ),
    hold: (paused: boolean) =>
      changeClocks(
        (d, now) => ({ timer: held(d.timer, paused, now) }),
        () => clocksApi.holdTimer(id, paused ? "pause" : "resume"),
      ),
    removeTimer: () =>
      changeClocks(
        () => ({ timer: null }),
        () => clocksApi.removeTimer(id),
      ),
    /** План или факт в минутах; null очищает. */
    setTracking: (patch: Partial<TimeTracking>) => changeTracking(() => patch),
    /** Прибавить к факту — предложение после остановки секундомера (KT-D4). */
    addToFact: (minutes: number) =>
      changeTracking((tracking) => ({
        fact_minutes: Math.min(TRACKED_MINUTES_MAX, (tracking?.fact_minutes ?? 0) + minutes),
      })),
  };
}

export type ClockActions = ReturnType<typeof clockActions>;
