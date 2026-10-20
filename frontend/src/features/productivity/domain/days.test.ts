import { describe, it } from "vitest";

import { dayFromToday, dayPeriod, daysAgo } from "./days";
import assert from "node:assert/strict";

const NOW = Date.UTC(2026, 9, 7, 23, 30);

describe("calendar days", () => {
  it("counts calendar days in the zone, not 24-hour spans", () => {
    assert.equal(daysAgo("2026-10-07T00:10:00Z", NOW, "UTC"), 0);
    assert.equal(daysAgo("2026-10-06T23:59:00Z", NOW, "UTC"), 1);
    assert.equal(daysAgo("2026-09-29T09:00:00Z", NOW, "UTC"), 8);
    // 23:30 UTC 7 октября — уже 8-е в Москве: вчерашнее для неё — 7-е.
    assert.equal(daysAgo("2026-10-07T00:10:00Z", NOW, "Europe/Moscow"), 1);
  });

  it("finds a day from today in the zone as UTC midnight", () => {
    assert.equal(dayFromToday(9, NOW, "UTC").toISOString(), "2026-10-16T00:00:00.000Z");
    assert.equal(dayFromToday(9, NOW, "Europe/Moscow").toISOString(), "2026-10-17T00:00:00.000Z");
  });

  it("names the part of the day", () => {
    assert.equal(dayPeriod(4), "evening");
    assert.equal(dayPeriod(5), "morning");
    assert.equal(dayPeriod(12), "afternoon");
    assert.equal(dayPeriod(18), "evening");
  });
});
