import type { Breadcrumb } from "./contract";
import type { ErrorSeverity, PlatformComponent } from "./dimensions";

/* ---------- POST /admin/errors/ingest ---------- */

/**
 * Sent by the desktop clients (and platform services) for every captured error. Authenticated with
 * the client's ingest key in `Authorization: Bearer <key>`, not an admin session.
 */
export type IngestEventRequest = {
  /** "macos" | "windows" for desktop clients; "web" | "api" | "agent" for platform services. */
  platform: "macos" | "windows" | PlatformComponent;
  /** Semantic version of the client build, e.g. "2.5.0". */
  app_version: string;
  /** e.g. "macOS 15.5 (24F74)" or "Windows 11 24H2 (26100.4061)". */
  os_version: string;
  /** Exception message, e.g. "Unexpectedly found nil while unwrapping an Optional value". */
  message: string;
  /** e.g. "NullReferenceException"; defaults to "Error". */
  exception_type?: string;
  /** Raw stack trace as the runtime prints it, innermost frame first; one frame per line. */
  stack: string;
  /** Grouping key; when omitted the server derives one from the exception type and top frame. */
  fingerprint?: string;
  /** Signed-in user, if any. */
  user_id?: string | null;
  /** Defaults to "error"; unhandled crashes are "critical". */
  severity?: ErrorSeverity;
  /** e.g. "MacBookPro18,3" or "Dell XPS 13 9340". */
  device?: string;
  /** BCP 47, e.g. "ru-RU". */
  locale?: string;
  /** Last ~50 breadcrumbs, oldest first. */
  breadcrumbs?: Breadcrumb[];
  /** Free-form key/value pairs, e.g. { "release_channel": "beta" }. */
  tags?: Record<string, string>;
  /** When it happened on the device; defaults to the time the server received it. */
  timestamp?: string;
};

export type IngestEventResponse = {
  event_id: string;
  issue_id: string;
  /** True when this fingerprint had not been seen before. */
  is_new_issue: boolean;
  /** True when a resolved issue happened again and was reopened as "new". */
  is_regression: boolean;
};
