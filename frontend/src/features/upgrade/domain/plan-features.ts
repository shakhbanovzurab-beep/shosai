import type { Entitlements, Plan, PlanId, TeamSize } from "./contract";

/*
 * What a plan card and the comparison table show, as codes and numbers; the UI words them in the
 * interface language. Lines the admin wrote for a plan (`plan.features`) are passed through as written.
 */

/** Plans arrive cheapest first, so a plan further along the list is an upgrade. */
export function isUpgrade(plans: Plan[], from: PlanId, to: PlanId) {
  return plans.findIndex((p) => p.id === to) > plans.findIndex((p) => p.id === from);
}

const MB = 1024 * 1024;
const GB = 1024 * MB;

/** A storage amount: per user on a team plan, a starting point on a custom-priced plan ("from 250 GB"). */
export type Storage = { bytes: number; basis: "plan" | "perUser" | "from" } | "unlimited";

function storage(value: number | null, unit: number, plan: Plan): Storage {
  if (value === null) return "unlimited";
  const bytes = value * unit;
  if (plan.price === null) return { bytes, basis: "from" };
  return { bytes, basis: plan.seats ? "perUser" : "plan" };
}

/** The extras a plan can add; billing and member management come together on team plans, so they share one line. */
export type Capability =
  | "shared_workspace"
  | "member_management"
  | "centralized_billing"
  | "billing_and_users"
  | "admin_controls"
  | "sso"
  | "priority_support"
  | "usage_analytics";

const CAPABILITIES = [
  "shared_workspace",
  "member_management",
  "centralized_billing",
  "admin_controls",
  "sso",
  "priority_support",
  "usage_analytics",
] as const satisfies readonly (keyof Entitlements & Capability)[];

/** One line on a plan card; `included: false` is shown crossed out. */
export type Highlight =
  | { kind: "custom"; text: string; included: true }
  | { kind: "meetings"; minutes: number | null; included: boolean }
  | { kind: "fileManager" | "knowledge"; storage: Storage | null; included: boolean }
  | { kind: "capability"; capability: Capability; included: true };

/**
 * The card list: the plan's own lines from the admin, then meetings, storage and the extras that the
 * plan before it (in catalog order) doesn't already have, since its first line is "Everything in …".
 */
export function planHighlights(plan: Plan, previous?: Plan): Highlight[] {
  const e = plan.entitlements;
  const lines: Highlight[] = plan.features.map((text) => ({ kind: "custom", text, included: true }));
  lines.push({ kind: "meetings", minutes: e.meeting_minutes_per_month, included: e.meeting_minutes_per_month !== 0 });
  const files = e.file_manager_gb === 0 ? null : storage(e.file_manager_gb, GB, plan);
  lines.push({ kind: "fileManager", storage: files, included: files !== null });
  const knowledge = e.knowledge_base_mb === 0 ? null : storage(e.knowledge_base_mb, MB, plan);
  lines.push({ kind: "knowledge", storage: knowledge, included: knowledge !== null });

  const isNew = (key: keyof Entitlements) => e[key] === true && previous?.entitlements[key] !== true;
  const together = isNew("member_management") && isNew("centralized_billing");
  for (const capability of CAPABILITIES) {
    if (!isNew(capability)) continue;
    const combined = together && (capability === "member_management" || capability === "centralized_billing");
    if (!combined) lines.push({ kind: "capability", capability, included: true });
    else if (capability === "member_management")
      lines.push({ kind: "capability", capability: "billing_and_users", included: true });
  }
  return lines;
}

/** A cell of the comparison table: a yes/no mark, or a value to word. */
export type Cell =
  | boolean
  | { kind: "unlimited" }
  | { kind: "minutes"; minutes: number }
  | { kind: "storage"; storage: Storage }
  | { kind: "users"; min: number; max: number | null }
  | { kind: "customUsers" };

const limitCell = (value: number | null, cell: (value: number) => Cell): Cell => {
  if (value === null) return { kind: "unlimited" };
  if (value === 0) return false;
  return cell(value);
};

export type ComparisonRow =
  | "meetings"
  | "fileManager"
  | "knowledge"
  | "apps"
  | "users"
  | "sharedWorkspace"
  | "billingAndUsers"
  | "sso"
  | "adminControls"
  | "prioritySupport"
  | "usageAnalytics";

export const COMPARISON_ROWS: { row: ComparisonRow; cell: (plan: Plan) => Cell }[] = [
  {
    row: "meetings",
    cell: ({ entitlements: e }) => limitCell(e.meeting_minutes_per_month, (minutes) => ({ kind: "minutes", minutes })),
  },
  {
    row: "fileManager",
    cell: (plan) =>
      limitCell(plan.entitlements.file_manager_gb, (v) => ({ kind: "storage", storage: storage(v, GB, plan) })),
  },
  {
    row: "knowledge",
    cell: (plan) =>
      limitCell(plan.entitlements.knowledge_base_mb, (v) => ({ kind: "storage", storage: storage(v, MB, plan) })),
  },
  { row: "apps", cell: () => true },
  {
    row: "users",
    cell: (plan) => {
      if (plan.seats) return { kind: "users", min: plan.seats.min, max: plan.seats.max };
      return plan.price === null ? { kind: "customUsers" } : { kind: "users", min: 1, max: 1 };
    },
  },
  { row: "sharedWorkspace", cell: (plan) => plan.entitlements.shared_workspace },
  { row: "billingAndUsers", cell: ({ entitlements: e }) => e.member_management && e.centralized_billing },
  { row: "sso", cell: (plan) => plan.entitlements.sso },
  { row: "adminControls", cell: (plan) => plan.entitlements.admin_controls },
  { row: "prioritySupport", cell: (plan) => plan.entitlements.priority_support },
  { row: "usageAnalytics", cell: (plan) => plan.entitlements.usage_analytics },
];

/** Team sizes on the sales form, as ranges of people; `max: null` is "or more". */
export const TEAM_SIZE_RANGES = {
  "1-10": { min: 1, max: 10 },
  "11-50": { min: 11, max: 50 },
  "51-200": { min: 51, max: 200 },
  "201-1000": { min: 201, max: 1000 },
  "1000+": { min: 1000, max: null },
} as const satisfies Record<TeamSize, { min: number; max: number | null }>;
