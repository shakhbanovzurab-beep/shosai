import type { ErrorEventSummary, IssueDetail, UpdateIssueRequest } from "../domain/contract";
import { toIssue } from "./list";
import { ASSIGNEES, USERS } from "./reference";
import { store } from "./seed";

export function getIssue(id: string): IssueDetail | null {
  const data = store();
  const issue = data.issues.get(id);
  if (!issue) return null;
  const events = data.events.filter((event) => event.issue_id === id);
  const latest = events.at(-1);
  if (!latest) return null;
  const users = new Set(events.flatMap((event) => (event.user_id ? [event.user_id] : [])));
  const stats = { count: events.length, users, first: events[0].at, last: latest.at };
  const recent: ErrorEventSummary[] = events
    .slice(-10)
    .reverse()
    .map((event) => ({
      id: event.id,
      received_at: new Date(event.at).toISOString(),
      app_version: event.app_version,
      os_version: event.os_version,
      device: event.device,
      user_id: event.user_id,
    }));
  const tags = {
    source: issue.component ?? issue.source,
    severity: issue.severity,
    app_version: latest.app_version,
    os: latest.os_version,
    device: latest.device,
    ...issue.tags,
  };
  const user = latest.user_id
    ? (USERS.get(latest.user_id) ?? { id: latest.user_id, name: latest.user_id, email: "—" })
    : null;

  return {
    ...toIssue(issue, stats, latest.app_version),
    exception_type: issue.exception_type,
    message: issue.message,
    stack: issue.frames,
    breadcrumbs: issue.breadcrumbs,
    context: {
      device: latest.device,
      os_version: latest.os_version,
      app_version: latest.app_version,
      locale: issue.locale,
    },
    user,
    tags: Object.entries(tags).map(([key, value]) => ({ key, value })),
    recent_events: recent,
    support_ticket: issue.ticket,
    assignees: ASSIGNEES,
  };
}

/** Applies a PATCH; "unknown_assignee" when the assignee id isn't an admin. */
export function updateIssue(id: string, patch: UpdateIssueRequest): IssueDetail | null | "unknown_assignee" {
  const issue = store().issues.get(id);
  if (!issue) return null;
  if (patch.assignee && !ASSIGNEES.some((assignee) => assignee.id === patch.assignee)) return "unknown_assignee";
  if (patch.status) issue.status = patch.status;
  if (patch.assignee !== undefined) issue.assignee_id = patch.assignee;
  return getIssue(id);
}
