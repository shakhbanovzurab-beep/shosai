/**
 * Admin › Errors API contract, shared by the `/admin/errors` screens and the route handlers in
 * `../server` (served at `src/app/api/admin/errors`). They forward to `${BACKEND_API_URL}/v1/admin/errors*`
 * when it is set and otherwise answer from the in-memory demo in `../server/`. snake_case to match
 * Pydantic; errors are FastAPI's `{ "detail": string }`. Timestamps are ISO 8601 strings in UTC.
 *
 * GET   /admin/errors?source=&severity=&status=&version=&period=&sort=&order=&page=  → IssuesResponse
 * GET   /admin/errors/{id}                                                       → IssueDetail
 * PATCH /admin/errors/{id}            (UpdateIssueRequest)                       → IssueDetail
 * POST  /admin/errors/ingest          (IngestEventRequest, called by clients)   → 202 IngestEventResponse
 *
 * Events with the same `fingerprint` are grouped into one issue. Counts in the list (events, users)
 * cover the selected period and app version; the KPIs always cover the last 24 hours.
 *
 * Dimensions: `./dimensions`; their labels: `./labels`; the list query and its URL form: `./query`;
 * the ingest payload: `./ingest`; request validation: `./schemas`.
 */

import type { ErrorSeverity, ErrorSource, IssueStatus, PlatformComponent } from "./dimensions";

/* ---------- GET /admin/errors ---------- */

/** An admin who can own an issue. */
export type Assignee = { id: string; name: string; email: string };

/** One issue: all events sharing a fingerprint. */
export type ErrorIssue = {
  id: string;
  /** Grouping key sent by the client or derived by the server from the exception type and top in-app frame. */
  fingerprint: string;
  /** Exception type and message, e.g. "TypeError: Cannot read properties of undefined". */
  title: string;
  /** Where it was thrown: the top in-app frame, e.g. "ChatThread.render (chat-thread.tsx)". */
  culprit: string;
  source: ErrorSource;
  platform_component: PlatformComponent | null;
  severity: ErrorSeverity;
  status: IssueStatus;
  assignee: Assignee | null;
  first_seen: string;
  last_seen: string;
  /** Events in the selected period (and version, if filtered). */
  event_count: number;
  /** Distinct users in the selected period (and version, if filtered). */
  user_count: number;
  /** App version of the most recent event; for the platform, the deployed build. */
  latest_version: string;
};

/** Crash-free sessions of a desktop client over the last 24 hours versus the 24 hours before. */
export type CrashFreeRate = {
  source: Exclude<ErrorSource, "platform">;
  /** 0–1. */
  rate: number;
  previous_rate: number;
  sessions: number;
};

export type ErrorsKpis = {
  new_issues_24h: number;
  new_issues_prev_24h: number;
  events_24h: number;
  events_prev_24h: number;
  affected_users_24h: number;
  affected_users_prev_24h: number;
  crash_free: CrashFreeRate[];
};

/** Events per bucket and source; buckets are hours for "24h" and days otherwise. */
export type TimelinePoint = { bucket_start: string } & Record<ErrorSource, number>;

export type IssuesResponse = {
  items: ErrorIssue[];
  /** Issues matching the filters, across all pages. */
  total: number;
  page: number;
  page_size: number;
  kpis: ErrorsKpis;
  timeline: { bucket: "hour" | "day"; points: TimelinePoint[] };
  /** App versions seen in the period, newest first, for the version filter. */
  versions: string[];
  /** Everyone an issue can be assigned to. */
  assignees: Assignee[];
};

/* ---------- GET /admin/errors/{id} ---------- */

export type StackFrame = {
  function: string;
  file: string;
  line: number;
  column: number | null;
  /** Our code, as opposed to a framework or system library; collapsed frames are the others. */
  in_app: boolean;
  /** Source around the line, when the client sent it, with `line` among them. */
  context: { line: number; code: string }[] | null;
};

export type BreadcrumbCategory = "navigation" | "http" | "ui" | "console" | "system";
export type BreadcrumbLevel = "info" | "warning" | "error";

/** What happened just before the error, oldest first. */
export type Breadcrumb = {
  timestamp: string;
  category: BreadcrumbCategory;
  level: BreadcrumbLevel;
  message: string;
};

export type ErrorEventSummary = {
  id: string;
  received_at: string;
  app_version: string;
  os_version: string;
  device: string;
  user_id: string | null;
};

export type IssueUser = { id: string; name: string; email: string };

/** In the detail, `event_count` and `user_count` are all-time totals, independent of any list filter. */
export type IssueDetail = ErrorIssue & {
  exception_type: string;
  message: string;
  /** Frames of the latest event, innermost (where it was thrown) first. */
  stack: StackFrame[];
  /** Breadcrumbs of the latest event. */
  breadcrumbs: Breadcrumb[];
  /** Device and environment of the latest event. */
  context: { device: string; os_version: string; app_version: string; locale: string | null };
  /** The user of the latest event, if signed in. */
  user: IssueUser | null;
  tags: { key: string; value: string }[];
  /** Latest events, newest first (at most 10). */
  recent_events: ErrorEventSummary[];
  /** The support conversation that reported this issue, if any. */
  support_ticket: { id: string; number: number; subject: string } | null;
  assignees: Assignee[];
};

/* ---------- PATCH /admin/errors/{id} ---------- */

/** Any subset; `assignee` is an Assignee id, or null to unassign. */
export type UpdateIssueRequest = { status?: IssueStatus; assignee?: string | null };
