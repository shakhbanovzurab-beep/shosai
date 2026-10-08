/*
 * The people of the demo. One person is one account, wherever they are a member: the demo user is
 * the owner of Lumen and a member of the Northwind pilot workspace, and so is Priya.
 */

export const ME_ACCOUNT = "u-arham";

export type Person = { account: string; name: string; email: string };

/** The demo user. */
export const ME: Person = { account: ME_ACCOUNT, name: "Arham Khan", email: "arham@lumen.so" };

export const PEOPLE: Record<string, Person> = {
  "Arham Khan": ME,
  "Maya Chen": { account: "u-maya", name: "Maya Chen", email: "maya@lumen.so" },
  "Elena Petrova": { account: "u-elena", name: "Elena Petrova", email: "elena@lumen.so" },
  "Diego Alvarez": { account: "u-diego", name: "Diego Alvarez", email: "diego@lumen.so" },
  "Priya Nair": { account: "u-priya", name: "Priya Nair", email: "priya@lumen.so" },
  "Noah Kim": { account: "u-noah", name: "Noah Kim", email: "noah@lumen.so" },
  "Sofia Rossi": { account: "u-sofia", name: "Sofia Rossi", email: "sofia@lumen.so" },
  "Tom Becker": { account: "u-tom", name: "Tom Becker", email: "tom@lumen.so" },
  "Liam Turner": { account: "u-liam", name: "Liam Turner", email: "liam@northwind.com" },
  "Grace Ito": { account: "u-grace", name: "Grace Ito", email: "grace@northwind.com" },
};

const MINUTE = 60_000;
export const minutesAgo = (minutes: number) => new Date(Date.now() - minutes * MINUTE).toISOString();
export const HOUR = 60;
export const DAY = 24 * HOUR;

const DAY_MS = 86_400_000;
/** A calendar day relative to today, "2026-10-09". */
export const dayFromNow = (days: number) => new Date(Date.now() + days * DAY_MS).toISOString().slice(0, 10);

export const nextMonthStart = () => {
  const now = new Date();
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1)).toISOString();
};

/** The Team plan's price per seat in the demo catalog. */
export const TEAM_SEAT_CENTS = 2000;
