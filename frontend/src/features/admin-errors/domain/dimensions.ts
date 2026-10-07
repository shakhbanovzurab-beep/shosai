/** Dimensions of Admin › Errors: sources, severities, statuses, periods, with their Russian labels. */

/** Where the error happened: our platform (web app, API, agent runtime) or a desktop client. */
export type ErrorSource = "platform" | "macos" | "windows";
/** The part of the platform that reported it; null for desktop clients. */
export type PlatformComponent = "web" | "api" | "agent";
export type ErrorSeverity = "critical" | "error" | "warning";
export type IssueStatus = "new" | "in_progress" | "resolved" | "ignored";
export type ErrorPeriod = "24h" | "7d" | "14d" | "30d";
export type IssueSort = "last_seen" | "first_seen" | "events" | "users";
export type SortOrder = "asc" | "desc";

export const ERROR_SOURCES = [
  { id: "platform", label: "Платформа" },
  { id: "macos", label: "macOS" },
  { id: "windows", label: "Windows" },
] as const satisfies readonly { id: ErrorSource; label: string }[];

export const PLATFORM_COMPONENTS = [
  { id: "web", label: "Веб" },
  { id: "api", label: "API" },
  { id: "agent", label: "Агент" },
] as const satisfies readonly { id: PlatformComponent; label: string }[];

/** Most severe first. */
export const ERROR_SEVERITIES = [
  { id: "critical", label: "Критическая" },
  { id: "error", label: "Ошибка" },
  { id: "warning", label: "Предупреждение" },
] as const satisfies readonly { id: ErrorSeverity; label: string }[];

export const ISSUE_STATUSES = [
  { id: "new", label: "Новая" },
  { id: "in_progress", label: "В работе" },
  { id: "resolved", label: "Решена" },
  { id: "ignored", label: "Игнорируется" },
] as const satisfies readonly { id: IssueStatus; label: string }[];

export const ERROR_PERIODS = [
  { id: "24h", label: "24 часа", hours: 24 },
  { id: "7d", label: "7 дней", hours: 24 * 7 },
  { id: "14d", label: "14 дней", hours: 24 * 14 },
  { id: "30d", label: "30 дней", hours: 24 * 30 },
] as const satisfies readonly { id: ErrorPeriod; label: string; hours: number }[];

export const ISSUE_SORTS = ["last_seen", "first_seen", "events", "users"] as const satisfies readonly IssueSort[];

export const ISSUES_PAGE_SIZE = 10;
