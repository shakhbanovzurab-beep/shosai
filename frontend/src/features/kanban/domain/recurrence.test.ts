import { describe, expect, it } from "vitest";

import {
  addDays,
  firstDue,
  isValidRecurrence,
  nextDue,
  occurrenceFrom,
  recurrenceFor,
  shiftedStart,
  weekdayOf,
  weekdaysFrom,
} from "./recurrence";
import { type Recurrence, WEEKDAYS, type Weekday } from "./tasks-contract";

// Все дни года: високосного и обычного.
const daysOf = (year: number) => {
  const days: string[] = [];
  for (let day = `${year}-01-01`; day.startsWith(String(year)); day = addDays(day, 1)) days.push(day);
  return days;
};
const YEARS = [2027, 2028];
const DAYS = YEARS.flatMap(daysOf);

describe("occurrences", () => {
  it("knows the weekday of every day", () => {
    expect(weekdayOf("2026-10-21")).toBe("wed");
    expect(weekdayOf("2026-10-25")).toBe("sun");
    expect(weekdayOf("2026-10-26")).toBe("mon");
  });

  it("a daily task comes the next day after its due day when that day has not passed", () => {
    for (const due of DAYS) expect(nextDue({ every: "day" }, due, due)).toBe(addDays(due, 1));
  });

  it("skips the dates already past and never counts from the completion day", () => {
    expect(nextDue({ every: "day" }, "2026-10-19", "2026-10-21")).toBe("2026-10-21");
    // Еженедельно по пятницам, закрыта рано: следующая пятница после исходного срока, а не после закрытия.
    expect(nextDue({ every: "week", weekdays: ["fri"] }, "2026-10-23", "2026-10-20")).toBe("2026-10-30");
    expect(nextDue({ every: "week", weekdays: ["fri"] }, "2026-10-09", "2026-10-21")).toBe("2026-10-23");
  });

  it("finds the first chosen weekday for every weekday set and every day", () => {
    const sets: Weekday[][] = [["mon"], ["tue", "thu"], ["sat", "sun"], [...WEEKDAYS]];
    for (const weekdays of sets)
      for (const day of DAYS) {
        const found = occurrenceFrom({ every: "week", weekdays }, day);
        expect(weekdays).toContain(weekdayOf(found));
        expect(found >= day && found <= addDays(day, 6)).toBe(true);
        for (let d = day; d < found; d = addDays(d, 1)) expect(weekdays).not.toContain(weekdayOf(d));
      }
  });

  it("puts a monthly day 29–31 on the last day of a shorter month, for every month day", () => {
    for (let day = 1; day <= 31; day++)
      for (const from of DAYS) {
        const found = occurrenceFrom({ every: "month", day }, from);
        expect(found >= from).toBe(true);
        const [year, month, dom] = found.split("-").map(Number);
        const last = new Date(Date.UTC(year, month, 0)).getUTCDate();
        expect(dom).toBe(Math.min(day, last));
      }
    expect(nextDue({ every: "month", day: 31 }, "2027-01-31", "2027-01-31")).toBe("2027-02-28");
    expect(nextDue({ every: "month", day: 31 }, "2028-01-31", "2028-01-31")).toBe("2028-02-29");
    expect(nextDue({ every: "month", day: 1 }, "2027-12-01", "2027-12-05")).toBe("2028-01-01");
  });

  it("gives a task without a due day the first date from today", () => {
    expect(firstDue({ every: "day" }, "2026-10-21")).toBe("2026-10-21");
    expect(firstDue({ every: "week", weekdays: ["mon"] }, "2026-10-21")).toBe("2026-10-26");
  });

  it("keeps a range's length", () => {
    expect(shiftedStart("2026-10-20", "2026-10-23", "2026-10-30")).toBe("2026-10-27");
    expect(shiftedStart(null, "2026-10-23", "2026-10-30")).toBeNull();
  });

  it("refuses a week with no day and a month day out of range", () => {
    expect(isValidRecurrence({ every: "week", weekdays: [] })).toBe(false);
    expect(isValidRecurrence({ every: "week", weekdays: ["mon", "mon"] })).toBe(false);
    expect(isValidRecurrence({ every: "month", day: 0 })).toBe(false);
    expect(isValidRecurrence({ every: "month", day: 31 })).toBe(true);
  });
});

describe("choosing how a task repeats", () => {
  it("starts a weekly or monthly rule from the task's day", () => {
    expect(recurrenceFor("week", null, "2026-10-22")).toEqual({ every: "week", weekdays: ["thu"] });
    expect(recurrenceFor("month", null, "2026-10-22")).toEqual({ every: "month", day: 22 });
    expect(recurrenceFor("week", null, null)).toEqual({ every: "week", weekdays: ["mon"] });
    expect(recurrenceFor("month", null, null)).toEqual({ every: "month", day: 1 });
  });

  it("keeps the chosen days when the kind stays, and clears the rule for never", () => {
    const weekly: Recurrence = { every: "week", weekdays: ["tue", "fri"] };
    expect(recurrenceFor("week", weekly, "2026-10-22")).toBe(weekly);
    expect(recurrenceFor("month", weekly, "2026-10-22")).toEqual({ every: "month", day: 22 });
    expect(recurrenceFor("day", weekly, null)).toEqual({ every: "day" });
    expect(recurrenceFor("never", weekly, null)).toBeNull();
  });

  it("orders the weekdays from the first day of the person's week", () => {
    expect(weekdaysFrom(1)).toEqual([...WEEKDAYS]);
    expect(weekdaysFrom(7)).toEqual(["sun", "mon", "tue", "wed", "thu", "fri", "sat"]);
    expect(weekdaysFrom(6)).toEqual(["sat", "sun", "mon", "tue", "wed", "thu", "fri"]);
  });
});
