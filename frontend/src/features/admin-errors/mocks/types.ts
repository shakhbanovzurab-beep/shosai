import type { Breadcrumb, IssueDetail, StackFrame } from "../domain/contract";
import type { ErrorSeverity, ErrorSource, IssueStatus, PlatformComponent } from "../domain/dimensions";

/*
 * In-memory error tracker for the demo: a seeded set of issues and their events, generated relative
 * to the time the store was created (and re-seeded after 12 hours so "last 24 hours" stays lively).
 * Events posted to the ingest endpoint are grouped into issues by fingerprint, like the real backend.
 */

export const HOUR = 3_600_000;
export const DAY = 24 * HOUR;

export type StoredIssue = {
  id: string;
  fingerprint: string;
  exception_type: string;
  message: string;
  culprit: string;
  source: ErrorSource;
  component: PlatformComponent | null;
  severity: ErrorSeverity;
  status: IssueStatus;
  assignee_id: string | null;
  frames: StackFrame[];
  breadcrumbs: Breadcrumb[];
  tags: Record<string, string>;
  locale: string | null;
  ticket: IssueDetail["support_ticket"];
};

export type StoredEvent = {
  id: string;
  issue_id: string;
  at: number;
  app_version: string;
  os_version: string;
  device: string;
  user_id: string | null;
};

export type Store = { seededAt: number; issues: Map<string, StoredIssue>; events: StoredEvent[] };

export type FrameSeed = [fn: string, file: string, line: number, inApp: boolean];

export type Template = {
  exception_type: string;
  message: string;
  source: ErrorSource;
  component: PlatformComponent | null;
  severity: ErrorSeverity;
  status: IssueStatus;
  assignee_id: string | null;
  /** Events per day while active. */
  rate: number;
  users: number;
  first_days_ago: number;
  last_hours_ago: number;
  frames: FrameSeed[];
  /** Source around the top in-app frame's line. */
  context?: string[];
  ticket?: IssueDetail["support_ticket"];
};
