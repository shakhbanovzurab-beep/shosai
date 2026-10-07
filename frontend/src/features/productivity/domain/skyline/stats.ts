import { buildGrid, type Cell, type ContributionDay, DAY_MS, dayMs, generateContributions } from "./contributions";

export type Streak = { days: number; start: string | null; end: string | null };
export type ContributionStats = {
  total: number;
  first: string | null;
  last: string | null;
  busiest: { count: number; date: string | null };
  longest: Streak;
  current: Streak;
};
export type MonthLabel = { week: number; label: string };
export type SkylineModel = ReturnType<typeof buildGrid> & { stats: ContributionStats; months: MonthLabel[] };

/** Total, busiest day, longest run, and the run that reaches today (or yesterday — today isn't over). */
export const computeStats = (cells: Cell[]): ContributionStats => {
  let total = 0;
  let best = 0;
  let bestDate: string | null = null;
  let run = 0;
  let runStart: string | null = null;
  let longest: Streak = { days: 0, start: null, end: null };
  for (const c of cells) {
    total += c.count;
    if (c.count > best) {
      best = c.count;
      bestDate = c.date;
    }
    if (c.count > 0) {
      if (run === 0) runStart = c.date;
      run++;
      if (run > longest.days) longest = { days: run, start: runStart, end: c.date };
    } else run = 0;
  }
  let j = cells.length - 1;
  if (j >= 0 && cells[j].count === 0) j--;
  const endAt = j;
  while (j >= 0 && cells[j].count > 0) j--;
  const days = endAt - j;
  const current: Streak =
    days > 0 ? { days, start: cells[j + 1].date, end: cells[endAt].date } : { days: 0, start: null, end: null };
  return {
    total,
    first: cells.length ? cells[0].date : null,
    last: cells.length ? cells[cells.length - 1].date : null,
    busiest: { count: best, date: bestDate },
    longest,
    current,
  };
};

/**
 * A label on each week whose first day starts a new month, in the interface language (`locale`); a cramped
 * first label is dropped.
 */
export const monthLabels = (cells: Cell[], weeks: number, locale: string): MonthLabel[] => {
  const fmt = new Intl.DateTimeFormat(locale, { month: "short", timeZone: "UTC" });
  const out: MonthLabel[] = [];
  let prev = -1;
  for (let w = 0; w < weeks; w++) {
    const c = cells[w * 7];
    if (!c) break;
    const m = +c.date.slice(5, 7);
    if (m !== prev) out.push({ week: w, label: fmt.format(dayMs(c.date)) });
    prev = m;
  }
  if (out.length > 1 && out[1].week - out[0].week < 3) out.shift();
  return out;
};

export const buildModel = (
  data: ContributionDay[] | undefined,
  endKey: number | null,
  seed: number,
  weekStart: number,
  locale: string,
): SkylineModel => {
  const dates = (data ?? []).map((d) => dayMs(d.date)).filter(Number.isFinite);
  const end = endKey ?? (dates.length ? Math.max(...dates) : Math.floor(Date.now() / DAY_MS) * DAY_MS);
  const grid = buildGrid(data ?? generateContributions(end, seed), end, weekStart);
  return { ...grid, stats: computeStats(grid.cells), months: monthLabels(grid.cells, grid.weeks, locale) };
};
