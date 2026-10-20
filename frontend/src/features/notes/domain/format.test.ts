import { describe, it } from "vitest";

import { formatMeetingDuration, formatTimestamp, getRecencyGroup } from "./format";
import assert from "node:assert/strict";

describe("formatMeetingDuration", () => {
  it("writes minutes, then hours and minutes, in the interface language", () => {
    assert.equal(formatMeetingDuration("en", 48), "48 min");
    assert.equal(formatMeetingDuration("en", 65), "1 hr 5 min");
    assert.equal(formatMeetingDuration("en", 120), "2 hr");
    assert.equal(formatMeetingDuration("ru", 65), "1 ч 5 мин");
  });
});

describe("getRecencyGroup", () => {
  const now = new Date("2026-10-07T08:00:00Z");
  it("buckets by UTC calendar day", () => {
    assert.equal(getRecencyGroup("2026-10-07T00:10:00Z", now, "UTC"), "today");
    assert.equal(getRecencyGroup("2026-10-06T23:50:00Z", now, "UTC"), "yesterday");
    assert.equal(getRecencyGroup("2026-10-02T09:00:00Z", now, "UTC"), "thisWeek");
    assert.equal(getRecencyGroup("2026-09-30T09:00:00Z", now, "UTC"), "earlier");
  });

  it("counts the days in the cabinet's zone", () => {
    // 23:50 UTC 6 октября — уже 7-е в Москве, где и «сейчас» 7-е.
    assert.equal(getRecencyGroup("2026-10-06T23:50:00Z", now, "Europe/Moscow"), "today");
  });
});

describe("formatTimestamp", () => {
  it("writes a moment as a player does, rounding the server's fractions of a second", () => {
    assert.equal(formatTimestamp(95), "1:35");
    assert.equal(formatTimestamp(2.7000000000000046), "0:03");
    assert.equal(formatTimestamp(59.6), "1:00");
  });
});
