import { describe, it } from "vitest";

import { advance, choosePreset, formatClock, initialTimer, parseTimer, pause, remainingMs, start } from "./timer";
import assert from "node:assert/strict";

const T0 = new Date(2026, 9, 7, 9, 0).getTime();
const MIN = 60_000;

describe("focus timer", () => {
  it("counts down while running and keeps the time left when paused", () => {
    const running = start(initialTimer("pomodoro", T0), T0);
    assert.equal(remainingMs(running, T0 + 10 * MIN), 15 * MIN);
    const paused = pause(running, T0 + 10 * MIN);
    assert.equal(remainingMs(paused, T0 + 60 * MIN), 15 * MIN);
    assert.equal(remainingMs(start(paused, T0 + 60 * MIN), T0 + 65 * MIN), 10 * MIN);
  });

  it("never goes below zero", () => {
    assert.equal(remainingMs(start(initialTimer("pomodoro", T0), T0), T0 + 99 * MIN), 0);
  });

  it("gives a long break after every fourth pomodoro", () => {
    let t = initialTimer("pomodoro", T0);
    const phases: string[] = [];
    for (let i = 0; i < 8; i++) {
      t = advance(t, T0, true);
      phases.push(t.phase);
    }
    assert.deepEqual(phases, ["break", "focus", "break", "focus", "break", "focus", "long_break", "focus"]);
    assert.equal(t.doneToday, 4);
    assert.equal(t.cycleDone, 0);
  });

  it("doesn't count a skipped focus session", () => {
    const t = advance(initialTimer("pomodoro", T0), T0, false);
    assert.equal(t.phase, "break");
    assert.equal(t.doneToday, 0);
  });

  it("starts today's count again on a new day, and keeps it when the preset changes", () => {
    const yesterday = advance(initialTimer("pomodoro", T0), T0, true);
    assert.equal(advance(advance(yesterday, T0, true), T0 + 24 * 60 * MIN, true).doneToday, 1);
    assert.equal(choosePreset(yesterday, "deep-work", T0).doneToday, 1);
    assert.equal(choosePreset(yesterday, "deep-work", T0).remainingMs, 90 * MIN);
  });

  it("formats the clock", () => {
    assert.equal(formatClock(25 * MIN), "25:00");
    assert.equal(formatClock(61_000), "1:01");
    assert.equal(formatClock(90 * MIN), "1:30:00");
    assert.equal(formatClock(500), "0:01");
  });

  it("rejects saved data that isn't a timer", () => {
    assert.equal(parseTimer({ presetId: "nope" }), null);
    assert.ok(parseTimer(initialTimer("fifty", T0)));
  });
});
