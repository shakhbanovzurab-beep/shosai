import { describe, it } from "vitest";

import { formatMeetingDuration, getRecencyGroup } from "./format";
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
    assert.equal(getRecencyGroup("2026-10-07T00:10:00Z", now), "today");
    assert.equal(getRecencyGroup("2026-10-06T23:50:00Z", now), "yesterday");
    assert.equal(getRecencyGroup("2026-10-02T09:00:00Z", now), "thisWeek");
    assert.equal(getRecencyGroup("2026-09-30T09:00:00Z", now), "earlier");
  });
});
