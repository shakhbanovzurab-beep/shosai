/*
 * The demo's "now", injected rather than read from the system clock, so the scenario's days never
 * drift ("overdue by 1 day" stays 1 day). HUB_DEMO_NOW overrides it; the sample recordings in Notes
 * are dated around the default.
 */

export const DEFAULT_DEMO_NOW = "2026-10-06T15:00:00Z";

export const demoNow = () => new Date(process.env.HUB_DEMO_NOW ?? DEFAULT_DEMO_NOW);

const DAY_MS = 86_400_000;

const utcDay = (date: Date) => Math.floor(date.getTime() / DAY_MS);

/** Whole calendar days from `from` to `to` (UTC), never negative. */
export const daysBetween = (from: string | Date, to: string | Date) =>
  Math.max(0, utcDay(new Date(to)) - utcDay(new Date(from)));

export const addDays = (date: Date, days: number) => new Date(date.getTime() + days * DAY_MS);

/** A calendar day relative to now, at a given UTC time: `dayAt(now, -3, "10:00")`. */
export function dayAt(now: Date, offset: number, time: string) {
  const day = addDays(now, offset).toISOString().slice(0, 10);
  return new Date(`${day}T${time}:00Z`).toISOString();
}
