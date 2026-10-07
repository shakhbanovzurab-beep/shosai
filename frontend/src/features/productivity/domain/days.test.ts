import { dayFromToday, dayPeriod, daysAgo } from "./days";
import assert from "node:assert/strict";
import { describe, it } from "node:test";

const NOW = Date.UTC(2026, 9, 7, 23, 30);

describe("calendar days", () => {
  it("counts UTC calendar days, not 24-hour spans", () => {
    assert.equal(daysAgo("2026-10-07T00:10:00Z", NOW), 0);
    assert.equal(daysAgo("2026-10-06T23:59:00Z", NOW), 1);
    assert.equal(daysAgo("2026-09-29T09:00:00Z", NOW), 8);
  });

  it("finds a day from today as UTC midnight", () => {
    assert.equal(dayFromToday(9, NOW).toISOString(), "2026-10-16T00:00:00.000Z");
  });

  it("names the part of the day", () => {
    assert.equal(dayPeriod(4), "evening");
    assert.equal(dayPeriod(5), "morning");
    assert.equal(dayPeriod(12), "afternoon");
    assert.equal(dayPeriod(18), "evening");
  });
});
