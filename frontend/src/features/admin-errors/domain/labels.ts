import {
  ERROR_SEVERITIES,
  ERROR_SOURCES,
  type ErrorSeverity,
  type ErrorSource,
  ISSUE_STATUSES,
  type IssueStatus,
  PLATFORM_COMPONENTS,
  type PlatformComponent,
} from "./dimensions";

/* Russian labels for issue dimensions, shared by the list, the issue page and the summary. */

export const SOURCE_LABEL = Object.fromEntries(ERROR_SOURCES.map((s) => [s.id, s.label])) as Record<
  ErrorSource,
  string
>;
export const COMPONENT_LABEL = Object.fromEntries(PLATFORM_COMPONENTS.map((c) => [c.id, c.label])) as Record<
  PlatformComponent,
  string
>;
export const SEVERITY_LABEL = Object.fromEntries(ERROR_SEVERITIES.map((s) => [s.id, s.label])) as Record<
  ErrorSeverity,
  string
>;
export const STATUS_LABEL = Object.fromEntries(ISSUE_STATUSES.map((s) => [s.id, s.label])) as Record<
  IssueStatus,
  string
>;
