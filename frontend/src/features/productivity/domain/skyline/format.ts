import { dayMs } from "./contributions";
import type { ContributionStats } from "./stats";

/** What a headline number counts: contributions, or days in a row. */
export type StatUnit = "contributions" | "days";
export type StatId = "total" | "busiest" | "longest" | "current";

/** One headline number; the interface words its label and unit. `dates` is already formatted, or null. */
export type StatBlock = { id: StatId; count: number; unit: StatUnit; dates: string | null };

export type Formatters = ReturnType<typeof createFormatters>;

/**
 * Numbers and calendar days in the interface language ("Oct 7", "7 окт."). The days are UTC midnights, so they
 * are formatted in UTC and never shift by a time zone.
 */
export const createFormatters = (locale: string) => {
  const num = new Intl.NumberFormat(locale);
  const day = new Intl.DateTimeFormat(locale, { month: "short", day: "numeric", timeZone: "UTC" });
  const year = new Intl.DateTimeFormat(locale, { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
  const long = new Intl.DateTimeFormat(locale, { weekday: "long", month: "long", day: "numeric", timeZone: "UTC" });
  return {
    number: (n: number) => num.format(n),
    /** "Oct 7". */
    day: (date: string) => day.format(dayMs(date)),
    /** "Oct 7, 2026". */
    dayWithYear: (date: string) => year.format(dayMs(date)),
    /** "Wednesday, October 7". */
    long: (date: string) => long.format(dayMs(date)),
    /** "Oct 7 – 12", as the language writes a range; null without both ends. */
    range: (from: string | null, to: string | null, withYear = false) =>
      from && to ? (withYear ? year : day).formatRange(dayMs(from), dayMs(to)) : null,
  };
};

export const statBlocks = (stats: ContributionStats, fmt: Formatters): StatBlock[] => [
  { id: "total", count: stats.total, unit: "contributions", dates: fmt.range(stats.first, stats.last, true) },
  {
    id: "busiest",
    count: stats.busiest.count,
    unit: "contributions",
    dates: stats.busiest.date ? fmt.day(stats.busiest.date) : null,
  },
  { id: "longest", count: stats.longest.days, unit: "days", dates: fmt.range(stats.longest.start, stats.longest.end) },
  { id: "current", count: stats.current.days, unit: "days", dates: fmt.range(stats.current.start, stats.current.end) },
];
