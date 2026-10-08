import type { ErrorIssue, IssuesResponse, TimelinePoint } from "../domain/contract";
import { ERROR_PERIODS, ISSUES_PAGE_SIZE } from "../domain/dimensions";
import type { IssuesQuery } from "../domain/query";
import { compareVersions } from "./frames";
import { kpis } from "./kpis";
import { ASSIGNEES, USERS } from "./reference";
import { store } from "./seed";
import { DAY, HOUR, type Store, type StoredIssue } from "./types";

export type IssueStats = { count: number; users: Set<string>; first: number; last: number };

export function toIssue(issue: StoredIssue, stats: IssueStats, latestVersion: string): ErrorIssue {
  return {
    id: issue.id,
    fingerprint: issue.fingerprint,
    title: `${issue.exception_type}: ${issue.message}`,
    culprit: issue.culprit,
    source: issue.source,
    platform_component: issue.component,
    severity: issue.severity,
    status: issue.status,
    assignee: ASSIGNEES.find((assignee) => assignee.id === issue.assignee_id) ?? null,
    first_seen: new Date(stats.first).toISOString(),
    last_seen: new Date(stats.last).toISOString(),
    event_count: stats.count,
    user_count: stats.users.size,
    latest_version: latestVersion,
  };
}

/** First/last seen and the latest version, over all time. */
function lifetime(data: Store) {
  const result = new Map<string, { first: number; last: number; version: string }>();
  for (const event of data.events) {
    const entry = result.get(event.issue_id);
    if (!entry) result.set(event.issue_id, { first: event.at, last: event.at, version: event.app_version });
    else if (event.at >= entry.last) Object.assign(entry, { last: event.at, version: event.app_version });
  }
  return result;
}

function emptyTimeline(period: IssuesQuery["period"], now: number) {
  const hours = ERROR_PERIODS.find((option) => option.id === period)?.hours ?? 24 * 7;
  const bucket: "hour" | "day" = period === "24h" ? "hour" : "day";
  const bucketMs = bucket === "hour" ? HOUR : DAY;
  const bucketCount = Math.ceil((hours * HOUR) / bucketMs);
  const firstBucket = Math.floor(now / bucketMs) * bucketMs - (bucketCount - 1) * bucketMs;
  const points: TimelinePoint[] = Array.from({ length: bucketCount }, (_, index) => ({
    bucket_start: new Date(firstBucket + index * bucketMs).toISOString(),
    platform: 0,
    macos: 0,
    windows: 0,
  }));
  return { from: now - hours * HOUR, bucket, bucketMs, firstBucket, points };
}

const SORT_KEY: Record<IssuesQuery["sort"], (issue: ErrorIssue) => number> = {
  last_seen: (issue) => Date.parse(issue.last_seen),
  first_seen: (issue) => Date.parse(issue.first_seen),
  events: (issue) => issue.event_count,
  users: (issue) => issue.user_count,
};

/** Users matching a filter value: their id or their email. */
function matchingUserIds(value: string) {
  return new Set([...USERS.values()].filter((u) => u.id === value || u.email === value).map((u) => u.id));
}

export function listIssues(query: IssuesQuery): IssuesResponse {
  const data = store();
  const now = Date.now();
  const { from, bucket, bucketMs, firstBucket, points } = emptyTimeline(query.period, now);
  const userIds = query.user ? matchingUserIds(query.user) : null;
  const matchesIssue = (issue: StoredIssue) =>
    (!query.severity || issue.severity === query.severity) && (!query.status || issue.status === query.status);

  const versions = new Set<string>();
  const stats = new Map<string, IssueStats>();
  for (const event of data.events) {
    if (event.at < from) continue;
    const issue = data.issues.get(event.issue_id);
    if (!issue || (query.source && issue.source !== query.source)) continue;
    versions.add(event.app_version);
    if ((query.version && event.app_version !== query.version) || !matchesIssue(issue)) continue;
    if (userIds && !(event.user_id && userIds.has(event.user_id))) continue;
    const entry = stats.get(issue.id) ?? { count: 0, users: new Set<string>(), first: event.at, last: event.at };
    entry.count++;
    if (event.user_id) entry.users.add(event.user_id);
    entry.last = Math.max(entry.last, event.at);
    stats.set(issue.id, entry);
    const point = points[Math.floor((event.at - firstBucket) / bucketMs)];
    if (point) point[issue.source]++;
  }

  const life = lifetime(data);
  const direction = query.order === "asc" ? 1 : -1;
  const sortKey = SORT_KEY[query.sort];
  const rows = [...stats.entries()].flatMap(([id, entry]) => {
    const issue = data.issues.get(id);
    const all = life.get(id);
    return issue && all ? [toIssue(issue, { ...entry, first: all.first, last: all.last }, all.version)] : [];
  });
  rows.sort((a, b) => direction * (sortKey(a) - sortKey(b)) || a.id.localeCompare(b.id));

  const start = (query.page - 1) * ISSUES_PAGE_SIZE;
  return {
    items: rows.slice(start, start + ISSUES_PAGE_SIZE),
    total: rows.length,
    page: query.page,
    page_size: ISSUES_PAGE_SIZE,
    kpis: kpis(data, now),
    timeline: { bucket, points },
    versions: [...versions].sort(compareVersions).reverse(),
    assignees: ASSIGNEES,
  };
}
