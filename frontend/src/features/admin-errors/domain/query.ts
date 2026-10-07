import {
  ERROR_PERIODS,
  ERROR_SEVERITIES,
  ERROR_SOURCES,
  type ErrorPeriod,
  type ErrorSeverity,
  type ErrorSource,
  ISSUE_SORTS,
  ISSUE_STATUSES,
  type IssueSort,
  type IssueStatus,
  type SortOrder,
} from "./dimensions";

/* ---------- Query of GET /admin/errors ---------- */

/** Query string of the list. Omitted filters mean "all"; `version` is an exact app version. */
export type IssuesQuery = {
  source: ErrorSource | null;
  severity: ErrorSeverity | null;
  status: IssueStatus | null;
  version: string | null;
  /** Only events of one user, by email or user id (e.g. from a support conversation). */
  user: string | null;
  period: ErrorPeriod;
  sort: IssueSort;
  order: SortOrder;
  /** 1-based. */
  page: number;
};

export const DEFAULT_ISSUES_QUERY: IssuesQuery = {
  source: null,
  severity: null,
  status: null,
  version: null,
  user: null,
  period: "7d",
  sort: "last_seen",
  order: "desc",
  page: 1,
};

const pick = <T extends string>(value: string | null, allowed: readonly { id: T }[]): T | null =>
  allowed.some((option) => option.id === value) ? (value as T) : null;

/** Reads a list query from URL search params, dropping anything unknown. */
export function parseIssuesQuery(params: URLSearchParams): IssuesQuery {
  const sort = params.get("sort");
  const page = Number.parseInt(params.get("page") ?? "", 10);
  return {
    source: pick(params.get("source"), ERROR_SOURCES),
    severity: pick(params.get("severity"), ERROR_SEVERITIES),
    status: pick(params.get("status"), ISSUE_STATUSES),
    version: params.get("version")?.trim() || null,
    user: params.get("user")?.trim().toLowerCase() || null,
    period: pick(params.get("period"), ERROR_PERIODS) ?? DEFAULT_ISSUES_QUERY.period,
    sort: ISSUE_SORTS.find((option) => option === sort) ?? DEFAULT_ISSUES_QUERY.sort,
    order: params.get("order") === "asc" ? "asc" : "desc",
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

/** Writes a list query as URL search params, leaving out defaults so URLs stay short. */
export function issuesQueryToParams(query: IssuesQuery): URLSearchParams {
  const params = new URLSearchParams();
  for (const key of Object.keys(DEFAULT_ISSUES_QUERY) as (keyof IssuesQuery)[]) {
    const value = query[key];
    if (value !== null && value !== DEFAULT_ISSUES_QUERY[key]) params.set(key, String(value));
  }
  return params;
}
