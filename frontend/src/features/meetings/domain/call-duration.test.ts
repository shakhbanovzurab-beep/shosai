import { describe, expect, it } from "vitest";

import { callClock } from "./call-duration";

const START = Date.UTC(2026, 9, 28, 10, 0, 0);

describe("callClock", () => {
  it("shows minutes and seconds within the first hour", () => {
    expect(callClock(START, START)).toBe("0:00");
    expect(callClock(START, START + 247_900)).toBe("4:07");
    expect(callClock(START, START + 3_599_000)).toBe("59:59");
  });

  it("adds hours once the meeting passes one", () => {
    expect(callClock(START, START + 3_723_000)).toBe("1:02:03");
    expect(callClock(START, START + 36_000_000)).toBe("10:00:00");
  });

  it("never goes below zero when the device's clock is behind the server's", () => {
    expect(callClock(START, START - 5_000)).toBe("0:00");
  });
});
