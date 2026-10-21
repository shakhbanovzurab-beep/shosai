import { describe, expect, it } from "vitest";

import { dayKeyOf, localDay } from "./day-keys";

describe("calendar day keys", () => {
  it("reads a day back as the same key, across month, year and leap days", () => {
    for (const day of ["2026-10-21", "2026-12-31", "2027-01-01", "2028-02-29", "2026-03-29", "2026-10-25"])
      expect(dayKeyOf(localDay(day))).toBe(day);
  });

  it("makes the local midnight of the day", () => {
    const date = localDay("2026-10-21");
    expect([date.getFullYear(), date.getMonth(), date.getDate(), date.getHours()]).toEqual([2026, 9, 21, 0]);
  });
});
