import type { Formats } from "next-intl";

/**
 * Named formats for `format.dateTime(value, "short")`, `format.number(value, "percent")` and ICU arguments
 * such as `{when, date, short}`. Each language renders them its own way: "Sep 24" / "24 сент." / "9月24日".
 */
export const formats = {
  dateTime: {
    short: { month: "short", day: "numeric" },
    medium: { dateStyle: "medium" },
    long: { dateStyle: "long" },
    dateTime: { dateStyle: "medium", timeStyle: "short" },
    time: { timeStyle: "short" },
    // "Mon, Oct 5"; "Oct 5, 9:00 AM"; "Mon, Oct 5, 9:00 AM" (a meeting's day and start, no year).
    weekday: { weekday: "short", month: "short", day: "numeric" },
    shortDateTime: { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" },
    weekdayDateTime: { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" },
    /** "Fri": just the day of the week, as in "Reply by Fri". */
    weekdayName: { weekday: "short" },
    /** "Mon, Oct 12, 12:00 AM UTC": a moment worth naming its weekday and time zone, such as a limit's reset. */
    weekdayTime: {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short",
    },
    /** "12/2030": a month of a year in digits, as a card's expiry is written. */
    monthYear: { month: "2-digit", year: "numeric" },
  },
  number: {
    integer: { maximumFractionDigits: 0 },
    percent: { style: "percent", maximumFractionDigits: 0 },
    compact: { notation: "compact", maximumFractionDigits: 1 },
    minutes: { style: "unit", unit: "minute", unitDisplay: "short", maximumFractionDigits: 0 },
  },
} satisfies Formats;
