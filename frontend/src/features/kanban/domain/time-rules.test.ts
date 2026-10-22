import { describe, expect, it } from "vitest";

import { overPlan, stopwatchElapsed, timerLeft } from "./time-rules";

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
