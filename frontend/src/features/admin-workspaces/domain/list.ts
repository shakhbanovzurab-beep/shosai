import type { AdminWorkspace, WorkspaceStatus } from "./contract";

export const SORTS = [
  { id: "attention", label: "Сначала требующие внимания" },
  { id: "minutes", label: "По активности" },
  { id: "seats", label: "По занятым местам" },
  { id: "revenue", label: "По выручке" },
  { id: "created", label: "Сначала новые" },
] as const;
export type WorkspaceSort = (typeof SORTS)[number]["id"];

export type WorkspaceFilter = {
  q: string;
  status: WorkspaceStatus | null;
  plan: string | null;
  sort: WorkspaceSort;
};

export const DEFAULT_FILTER: WorkspaceFilter = { q: "", status: null, plan: null, sort: "attention" };

/** Seats nearly or fully taken: the next invitation will be refused. */
export const seatsTight = (w: AdminWorkspace) => w.seats_used >= w.plan.seats;

/** Suspended, unpaid, out of seats, or nobody active for two weeks. */
export function needsAttention(w: AdminWorkspace, now = Date.now()) {
  const quiet = w.last_active_at === null || now - Date.parse(w.last_active_at) > 14 * 86_400_000;
  return w.status === "suspended" || w.status === "past_due" || seatsTight(w) || quiet;
}

const RANK: Record<WorkspaceStatus, number> = { suspended: 0, past_due: 1, trialing: 3, active: 4 };

const COMPARE: Record<WorkspaceSort, (a: AdminWorkspace, b: AdminWorkspace) => number> = {
  attention: (a, b) =>
    Number(needsAttention(b)) - Number(needsAttention(a)) ||
    RANK[a.status] - RANK[b.status] ||
    a.name.localeCompare(b.name),
  minutes: (a, b) => b.minutes_month - a.minutes_month,
  seats: (a, b) => b.seats_used / b.plan.seats - a.seats_used / a.plan.seats,
  revenue: (a, b) => b.monthly_cents - a.monthly_cents,
  created: (a, b) => b.created_at.localeCompare(a.created_at),
};

export function applyFilter(rows: AdminWorkspace[], filter: WorkspaceFilter) {
  const words = filter.q.trim().toLowerCase();
  return rows
    .filter((w) => !filter.status || w.status === filter.status)
    .filter((w) => !filter.plan || w.plan.name === filter.plan)
    .filter(
      (w) =>
        !words ||
        [w.name, w.slug, w.owner?.name ?? "", w.owner?.email ?? ""].some((text) => text.toLowerCase().includes(words)),
    )
    .toSorted(COMPARE[filter.sort]);
}

/** The strip above the table: how many workspaces, seats, money and activity, and what needs a look. */
export function totals(rows: AdminWorkspace[]) {
  let seats = 0;
  let used = 0;
  let monthly = 0;
  let minutes = 0;
  let attention = 0;
  let active = 0;
  for (const w of rows) {
    seats += w.plan.seats;
    used += w.seats_used;
    if (w.status !== "suspended") monthly += w.monthly_cents;
    minutes += w.minutes_month;
    if (needsAttention(w)) attention++;
    if (w.status === "active" || w.status === "trialing") active++;
  }
  return { count: rows.length, active, seats, used, monthly, minutes, attention };
}
