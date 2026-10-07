import type { ErrorSource, PlatformComponent } from "../domain/dimensions";
import { ERROR_SEVERITIES } from "../domain/dimensions";
import type { IngestEventRequest, IngestEventResponse } from "../domain/ingest";
import { culpritOf, hash, parseStack } from "./frames";
import { store } from "./seed";
import type { StoredEvent, StoredIssue } from "./types";

const SEVERITY_RANK = new Map(ERROR_SEVERITIES.map((severity, index) => [severity.id, index]));

/** Groups a client event into its issue by fingerprint, creating or reopening the issue as needed. */
export function ingestEvent(request: IngestEventRequest): IngestEventResponse {
  const data = store();
  const desktop = request.platform === "macos" || request.platform === "windows";
  const source: ErrorSource = desktop ? (request.platform as ErrorSource) : "platform";
  const component = desktop ? null : (request.platform as PlatformComponent);
  const exceptionType = request.exception_type?.trim() || "Error";
  const severity = request.severity ?? "error";
  const frames = parseStack(request.stack);
  const culprit = culpritOf(frames);
  const fingerprint = request.fingerprint?.trim() || hash(`${source}:${exceptionType}:${culprit}`);
  const at = request.timestamp ? Math.min(Date.parse(request.timestamp), Date.now()) : Date.now();

  let issue = [...data.issues.values()].find((candidate) => candidate.fingerprint === fingerprint);
  const isNew = !issue;
  const isRegression = issue?.status === "resolved";
  if (!issue) {
    const created: StoredIssue = {
      id: `err_${hash(`${fingerprint}:${at}`).slice(0, 6)}`,
      fingerprint,
      exception_type: exceptionType,
      message: request.message,
      culprit,
      source,
      component,
      severity,
      status: "new",
      assignee_id: null,
      frames,
      breadcrumbs: [],
      tags: {},
      locale: null,
      ticket: null,
    };
    data.issues.set(created.id, created);
    issue = created;
  }

  if (isRegression) issue.status = "new";
  // An issue is as severe as its worst event.
  if ((SEVERITY_RANK.get(severity) ?? 9) < (SEVERITY_RANK.get(issue.severity) ?? 9)) issue.severity = severity;
  issue.frames = frames;
  issue.message = request.message;
  issue.breadcrumbs = request.breadcrumbs ?? [];
  issue.tags = { ...issue.tags, ...request.tags };
  issue.locale = request.locale ?? issue.locale;

  const event: StoredEvent = {
    id: `evt_${crypto.randomUUID().replaceAll("-", "").slice(0, 12)}`,
    issue_id: issue.id,
    at,
    app_version: request.app_version,
    os_version: request.os_version,
    device: request.device ?? "—",
    user_id: request.user_id ?? null,
  };
  // Keep events in time order; a late event from an offline client goes where it belongs.
  const index = data.events.findLastIndex((candidate) => candidate.at <= at);
  data.events.splice(index + 1, 0, event);

  return { event_id: event.id, issue_id: issue.id, is_new_issue: isNew, is_regression: isRegression };
}
