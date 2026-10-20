import { describe, it } from "vitest";

import { groupByDay, type Meeting } from "./meeting";
import { nearDay } from "./timing";
import assert from "node:assert/strict";

// 00:30 в Москве 21 октября — 21:30 UTC 20 октября.
const NOW = Date.parse("2026-10-20T21:30:00Z");

describe("meeting days", () => {
  it("names today, tomorrow and yesterday in the cabinet's zone", () => {
    assert.equal(nearDay("2026-10-21", NOW, "Europe/Moscow"), "today");
    assert.equal(nearDay("2026-10-21", NOW, "UTC"), "tomorrow");
    assert.equal(nearDay("2026-10-20", NOW, "Europe/Moscow"), "yesterday");
    assert.equal(nearDay("2026-10-25", NOW, "UTC"), null);
  });

  it("groups meetings under their days in the zone", () => {
    const meeting = (id: string, start: string) => ({ id, start }) as Meeting;
    const groups = groupByDay(
      [meeting("a", "2026-10-20T20:00:00Z"), meeting("b", "2026-10-20T22:00:00Z")],
      "Europe/Moscow",
    );

    assert.deepEqual(
      groups.map((group) => [group.day, group.meetings.map((m) => m.id)]),
      [
        ["2026-10-20", ["a"]],
        ["2026-10-21", ["b"]],
      ],
    );
  });
});
