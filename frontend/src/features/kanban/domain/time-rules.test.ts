import { describe, expect, it } from "vitest";

import type { Card } from "./tasks-contract";
import {
  columnTime,
  held,
  overPlan,
  started,
  stopped,
  stopwatchElapsed,
  timerBucket,
  timerLeft,
  trackingBucket,
  trackingSums,
  trackingWith,
} from "./time-rules";

const T0 = Date.parse("2026-10-22T09:00:00.000Z");
const MINUTE = 60_000;
const at = (minutes: number) => new Date(T0 + minutes * MINUTE).toISOString();

describe("time on a card", () => {
  it("adds the running span to the closed ones, and never counts back", () => {
    const stopwatch = { running_since: at(0), total_ms: 30 * MINUTE, by_column: {} };
    expect(stopwatchElapsed(stopwatch, T0 + 15 * MINUTE)).toBe(45 * MINUTE);
    expect(stopwatchElapsed(stopwatch, T0 - MINUTE)).toBe(30 * MINUTE);
    expect(stopwatchElapsed({ ...stopwatch, running_since: null }, T0 + 99 * MINUTE)).toBe(30 * MINUTE);
  });

  it("counts a running timer down past zero and holds a paused one", () => {
    const running = { length_ms: 60 * MINUTE, ends_at: at(60), paused_left_ms: null };
    expect(timerLeft(running, T0 + 50 * MINUTE)).toBe(10 * MINUTE);
    expect(timerLeft(running, T0 + 80 * MINUTE)).toBe(-20 * MINUTE);
    expect(timerLeft({ ...running, ends_at: null, paused_left_ms: 5 * MINUTE }, T0 + 999 * MINUTE)).toBe(5 * MINUTE);
  });

  it("marks the fact only when both are set and the fact passes the plan", () => {
    expect(overPlan({ plan_minutes: 60, fact_minutes: 61 })).toBe(true);
    expect(overPlan({ plan_minutes: 60, fact_minutes: 60 })).toBe(false);
    expect(overPlan({ plan_minutes: null, fact_minutes: 600 })).toBe(false);
  });
});

describe("a clock action before the server answers", () => {
  it("starts once, and a stop lays the running span into the task's column", () => {
    const first = started(null, T0);
    expect(started(first, T0 + MINUTE)).toBe(first);
    const stop = stopped(
      { ...first, by_column: { planned: 5 * MINUTE }, total_ms: 5 * MINUTE },
      T0 + 20 * MINUTE,
      "planned",
    );
    expect(stop).toEqual({ running_since: null, total_ms: 25 * MINUTE, by_column: { planned: 25 * MINUTE } });
    expect(stopped(stop, T0 + 99 * MINUTE, "planned")).toBe(stop);
  });

  it("pauses with what is left and resumes from it; plan and fact clear together", () => {
    const timer = { length_ms: 60 * MINUTE, ends_at: at(60), paused_left_ms: null };
    const paused = held(timer, true, T0 + 45 * MINUTE);
    expect(paused).toEqual({ length_ms: 60 * MINUTE, ends_at: null, paused_left_ms: 15 * MINUTE });
    expect(held(paused, false, T0 + 90 * MINUTE)?.ends_at).toBe(at(105));
    expect(trackingWith({ plan_minutes: 60, fact_minutes: null }, { plan_minutes: null })).toBeNull();
    expect(trackingWith(null, { fact_minutes: 30 })).toEqual({ plan_minutes: null, fact_minutes: 30 });
  });
});

describe("filters and column sums", () => {
  const card = (id: string, clocks: Partial<Card>) =>
    ({ id, stopwatch: null, timer: null, time_tracking: null, ...clocks }) as Card;

  it("puts a timer past zero among those whose time is up, and a plan without fact within plan", () => {
    const timer = { length_ms: MINUTE, ends_at: at(1), paused_left_ms: null };
    expect(timerBucket(timer, T0)).toBe("left");
    expect(timerBucket(timer, T0 + MINUTE)).toBe("up");
    expect(timerBucket(null, T0)).toBe("none");
    expect(trackingBucket({ plan_minutes: 60, fact_minutes: null })).toBe("within");
    expect(trackingBucket({ plan_minutes: null, fact_minutes: 600 })).toBe("none");
  });

  it("sums a column's own time with the running spans, and plan and fact of the cards shown", () => {
    const cards = {
      a: card("a", { stopwatch: { running_since: at(0), total_ms: 0, by_column: { building: 10 * MINUTE } } }),
      b: card("b", { time_tracking: { plan_minutes: 60, fact_minutes: 90 } }),
      c: card("c", { time_tracking: { plan_minutes: null, fact_minutes: 15 } }),
    };
    expect(columnTime(["a", "b"], cards, "building", T0 + 5 * MINUTE)).toBe(15 * MINUTE);
    expect(columnTime(["b"], cards, "building", T0)).toBeNull();
    expect(trackingSums(["a", "b", "c"], cards)).toEqual({ plan: 60, fact: 105 });
  });
});
