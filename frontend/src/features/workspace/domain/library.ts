import { dayIn, dayOf, daysBetween } from "@/i18n/calendar-days";

import type { Decision, TeamMeeting } from "./content-contract";

/* Filters of the shared Meetings library and the Decisions log, mirrored in the URL. */

export const MEETING_SCOPES = ["all", "mine"] as const;
export type MeetingScope = (typeof MEETING_SCOPES)[number];

export type LibraryQuery = { scope: MeetingScope; team: string | null; q: string };

const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value) ?? null;

export function parseLibraryQuery(params: Record<string, string | string[] | undefined>): LibraryQuery {
  return {
    scope: MEETING_SCOPES.find((s) => s === first(params.scope)) ?? "all",
    team: first(params.team),
    q: (first(params.q) ?? "").slice(0, 100),
  };
}

/** The query string of the Meetings or Decisions page for a query; the defaults stay out of it. */
export function librarySearch(query: Partial<LibraryQuery>) {
  const params = new URLSearchParams();
  if (query.scope && query.scope !== "all") params.set("scope", query.scope);
  if (query.team) params.set("team", query.team);
  if (query.q?.trim()) params.set("q", query.q.trim());
  const search = params.toString();
  return search ? `?${search}` : "";
}

const matches = (text: string, q: string) => text.toLowerCase().includes(q.trim().toLowerCase());

/** A meeting's team: the team it is shared with; null when it is for participants or everyone. */
export const meetingTeam = (meeting: TeamMeeting) =>
  meeting.visibility.level === "team" ? meeting.visibility.team_id : null;

export function filterMeetings(meetings: TeamMeeting[], query: LibraryQuery, meId: string) {
  return meetings.filter((m) => {
    if (query.scope === "mine" && m.organizer_id !== meId && !m.participants.some((p) => p.member_id === meId))
      return false;
    if (query.team && meetingTeam(m) !== query.team) return false;
    return !query.q.trim() || matches(m.title, query.q) || matches(m.summary, query.q);
  });
}

export function filterDecisions(decisions: Decision[], query: LibraryQuery) {
  return decisions.filter((d) => {
    if (query.team && d.team_id !== query.team) return false;
    return !query.q.trim() || matches(d.text, query.q) || matches(d.meeting_title, query.q);
  });
}

export type RecencyGroup = "thisWeek" | "lastWeek" | "earlier";

// Deprecated English headings, kept for screens that still show `label`; the UI words `key` instead.
const RECENCY_LABELS: Record<RecencyGroup, string> = {
  thisWeek: "This week",
  lastWeek: "Last week",
  earlier: "Earlier",
};

/**
 * Newest first under "This week", "Last week" and "Earlier" headings (`key`; `label` is the English heading).
 * Неделя начинается с понедельника и считается в поясе кабинета `zone`.
 */
export function groupByRecency<T>(items: T[], dateOf: (item: T) => string, now: number, zone: string) {
  const today = dayIn(now, zone);
  // Сколько дней прошло с понедельника этой недели.
  const sinceMonday = (new Date(`${today}T00:00:00Z`).getUTCDay() + 6) % 7;
  const groups: { key: RecencyGroup; label: string; items: T[] }[] = [];
  const sorted = items.toSorted((a, b) => dateOf(b).localeCompare(dateOf(a)));
  for (const item of sorted) {
    const days = daysBetween(today, dayOf(dateOf(item), zone)) + sinceMonday;
    let key: RecencyGroup = "earlier";
    if (days >= 0) key = "thisWeek";
    else if (days >= -7) key = "lastWeek";
    const last = groups.at(-1);
    if (last?.key === key) last.items.push(item);
    else groups.push({ key, label: RECENCY_LABELS[key], items: [item] });
  }
  return groups;
}
