import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { noteServerNow, serverTime, subscribeMinute } from "./server-clock";

const T0 = Date.parse("2026-10-22T09:00:30.000Z");

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(T0);
});
afterEach(() => {
  noteServerNow(new Date(Date.now()).toISOString());
  vi.useRealTimers();
});

describe("the server's minute", () => {
  it("wakes 300 running clocks with one timer, on the minute, and stops when nobody listens", () => {
    const calls = Array.from({ length: 300 }, () => vi.fn());
    const stops = calls.map((call) => subscribeMinute(call));
    expect(vi.getTimerCount()).toBe(1);
    vi.advanceTimersByTime(29_999);
    expect(calls[0]).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(calls.every((call) => call.mock.calls.length === 1)).toBe(true);
    expect(vi.getTimerCount()).toBe(1);
    for (const stop of stops) stop();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("follows the server's clock, ignoring network-sized differences", () => {
    const call = vi.fn();
    const stop = subscribeMinute(call);
    noteServerNow(new Date(T0 + 400).toISOString());
    expect(call).not.toHaveBeenCalled();
    noteServerNow(new Date(T0 + 5 * 60_000).toISOString());
    expect(call).toHaveBeenCalledOnce();
    expect(serverTime()).toBe(T0 + 5 * 60_000);
    stop();
  });
});
