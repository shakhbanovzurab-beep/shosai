export type ContributionDay = { date: string; count: number };
export type Cell = { date: string; count: number; level: number; week: number; day: number };

export const DAY_MS = 86400000;

/** UTC midnight → "YYYY-MM-DD". */
export const toKey = (ms: number): string => new Date(ms).toISOString().slice(0, 10);

/**
 * Any date-ish value → UTC midnight of its calendar day. "YYYY-MM-DD" strings
 * are read literally (no timezone drift), Date objects by their local day,
 * numbers as UTC timestamps.
 */
export const dayMs = (v: string | number | Date): number => {
  if (typeof v === "number") return Math.floor(v / DAY_MS) * DAY_MS;
  let date: Date;
  if (typeof v === "string") {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(v);
    if (m) return Date.UTC(+m[1], +m[2] - 1, +m[3]);
    date = new Date(v);
  } else date = v;
  return Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
};

/** mulberry32 — small, fast, deterministic. */
export const rng = (seed: number) => {
  let a = seed >>> 0;
  return (): number => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
};

/** A believable year for demos: quiet weekends, a few busy seasons, a drifting mood, the odd enormous day. */
export const generateContributions = (endMs: number, seed = 7, days = 371): ContributionDay[] => {
  const r = rng(seed);
  const bursts = Array.from({ length: 4 }, () => ({ at: r(), width: 0.035 + r() * 0.07, gain: 0.6 + r() * 1.1 }));
  const out: ContributionDay[] = [];
  let mood = 0.5;
  for (let i = 0; i < days; i++) {
    const ms = endMs - (days - 1 - i) * DAY_MS;
    const x = i / Math.max(1, days - 1);
    const dow = new Date(ms).getUTCDay();
    const weekend = dow === 0 || dow === 6;
    let heat = 0.2;
    for (const b of bursts) heat += b.gain * Math.exp(-((x - b.at) ** 2) / (2 * b.width ** 2));
    mood = mood * 0.85 + r() * 0.15;
    heat *= 0.55 + mood * 0.9;
    const pActive = Math.min(0.94, (weekend ? 0.22 : 0.5) + heat * 0.4);
    let count = 0;
    if (r() < pActive) count = 1 + Math.floor(-Math.log(1 - r()) * (1.2 + heat * 7) * (weekend ? 0.5 : 1));
    if (r() < 0.01) count += 18 + Math.floor(r() * 24);
    out.push({ date: toKey(ms), count });
  }
  return out;
};

/** 0 for an empty day, else 1–4 by quarters of `busy`. Anything at or past `busy` is 4. */
export const levelOf = (count: number, busy: number): number => {
  if (count <= 0) return 0;
  if (busy <= 0) return 4;
  return 1 + Math.min(3, Math.floor((count / busy) * 4));
};

/**
 * The grid: columns are weeks, rows are weekdays (row 0 = `weekStart`). It ends on
 * `endMs` and starts on the week containing the day one year earlier. Levels split
 * the non-zero days by their share of the 95th percentile, so one freak day can't
 * wash every other day out to level 1.
 */
export const buildGrid = (data: ContributionDay[], endMs: number, weekStart = 0) => {
  const counts = new Map<string, number>();
  for (const d of data) {
    if (typeof d.date !== "string") continue;
    const ms = dayMs(d.date);
    const c = Number(d.count);
    if (!Number.isFinite(ms) || !(c > 0) || !Number.isFinite(c)) continue;
    const k = toKey(ms);
    counts.set(k, (counts.get(k) ?? 0) + c);
  }
  let start = endMs - 364 * DAY_MS;
  start -= ((new Date(start).getUTCDay() - weekStart + 7) % 7) * DAY_MS;
  const cells: Cell[] = [];
  for (let ms = start, i = 0; ms <= endMs; ms += DAY_MS, i++) {
    const date = toKey(ms);
    cells.push({ date, count: counts.get(date) ?? 0, level: 0, week: Math.floor(i / 7), day: i % 7 });
  }
  const nz = cells
    .map((c) => c.count)
    .filter((c) => c > 0)
    .sort((a, b) => a - b);
  const busy = nz.length ? nz[Math.floor(0.95 * (nz.length - 1))] : 0;
  for (const c of cells) c.level = levelOf(c.count, busy);
  return {
    cells,
    weeks: cells.length ? cells[cells.length - 1].week + 1 : 0,
    max: nz.length ? nz[nz.length - 1] : 0,
  };
};
