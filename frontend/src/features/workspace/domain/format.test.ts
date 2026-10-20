import { describe, it } from "vitest";

import { daysFromToday, dueState, isThisYear } from "./format";
import { groupByRecency } from "./library";
import { dueGroup } from "./tasks";
import assert from "node:assert/strict";

// Среда, 21 октября 2026, 00:30 в Москве — ещё вторник, 20 октября, в UTC.
const NOW = Date.parse("2026-10-20T21:30:00Z");

describe("workspace calendar days", () => {
  it("counts days from today in the cabinet's zone, for a day and for a moment", () => {
    assert.equal(daysFromToday("2026-10-21", NOW, "Europe/Moscow"), 0);
    assert.equal(daysFromToday("2026-10-21", NOW, "UTC"), 1);
    assert.equal(daysFromToday("2026-10-20T20:00:00Z", NOW, "Europe/Moscow"), -1);
    assert.equal(isThisYear("2025-12-31", NOW, "UTC"), false);
  });

  it("grades a due day and groups a task by it in the zone", () => {
    assert.deepEqual(dueState("2026-10-20", NOW, "Europe/Moscow"), { days: -1, tone: "overdue" });
    assert.equal(dueGroup("2026-10-21", NOW, "Europe/Moscow"), "today");
    assert.equal(dueGroup("2026-10-21", NOW, "UTC"), "week");
  });

  it("starts this week on the zone's Monday", () => {
    const items = [{ at: "2026-10-19T09:00:00Z" }, { at: "2026-10-18T09:00:00Z" }, { at: "2026-10-01T09:00:00Z" }];
    const keys = groupByRecency(items, (item) => item.at, NOW, "Europe/Moscow").map((group) => group.key);

    assert.deepEqual(keys, ["thisWeek", "lastWeek", "earlier"]);
  });
});
