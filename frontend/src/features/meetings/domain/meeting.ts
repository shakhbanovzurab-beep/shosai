import { addDays, differenceInMinutes, isSameDay, startOfDay } from "date-fns";

/* A meeting as the Meetings page sees it: scheduled, in progress or over, wherever it takes place. */

export const MEETING_SOURCES = ["google_meet", "zoom", "teams", "whisperer", "in_person"] as const;
export type MeetingSource = (typeof MEETING_SOURCES)[number];

/** What Leo made of a recorded meeting; the full notes live in Notes. */
export type MeetingRecap = { noteId: string; summary: string; tasks: number; decisions: number };

export type Meeting = {
  id: string;
  title: string;
  /** ISO timestamps. */
  start: string;
  end: string;
  source: MeetingSource;
  /** The call's link; null for a meeting in person. A Whisperer room opens the LiveKit Meeting Room. */
  joinUrl: string | null;
  location: string | null;
  participants: { name: string }[];
  /** Null until the meeting has been recorded and summarized. */
  recap: MeetingRecap | null;
};

export type MeetingStatus = "live" | "upcoming" | "past";

export function meetingStatus(meeting: Meeting, now: number): MeetingStatus {
  if (Date.parse(meeting.end) <= now) return "past";
  return Date.parse(meeting.start) <= now ? "live" : "upcoming";
}

/** Join opens from ten minutes before the start until the end. */
const JOIN_EARLY_MINUTES = 10;

export const isJoinable = (meeting: Meeting, now: number) =>
  meeting.joinUrl !== null &&
  Date.parse(meeting.end) > now &&
  differenceInMinutes(new Date(meeting.start), new Date(now)) <= JOIN_EARLY_MINUTES;

/* ---------- Filters and sections ---------- */

export const MEETINGS_VIEWS = ["all", "upcoming", "live", "past"] as const;
export type MeetingsView = (typeof MEETINGS_VIEWS)[number];

export const parseMeetingsView = (value: unknown): MeetingsView =>
  MEETINGS_VIEWS.find((view) => view === value) ?? "all";

export const viewHref = (view: MeetingsView) => (view === "all" ? "/app/meetings" : `/app/meetings?view=${view}`);

export type MeetingBuckets = Record<MeetingStatus, Meeting[]>;

/** Live and upcoming soonest first; past most recent first. */
export function bucketMeetings(meetings: Meeting[], now: number): MeetingBuckets {
  const buckets: MeetingBuckets = { live: [], upcoming: [], past: [] };
  for (const meeting of meetings) buckets[meetingStatus(meeting, now)].push(meeting);
  const byStart = (a: Meeting, b: Meeting) => a.start.localeCompare(b.start);
  buckets.live.sort(byStart);
  buckets.upcoming.sort(byStart);
  buckets.past.sort((a, b) => byStart(b, a));
  return buckets;
}

/** The overview: what's on now and later today, the next few days, and the latest recaps. */
export function overviewSections(buckets: MeetingBuckets, now: number) {
  const today = new Date(now);
  const laterToday = buckets.upcoming.filter((m) => isSameDay(new Date(m.start), today));
  const tomorrow = startOfDay(addDays(today, 1)).getTime();
  return {
    live: buckets.live,
    laterToday,
    upcoming: buckets.upcoming.filter((m) => Date.parse(m.start) >= tomorrow).slice(0, 4),
    recent: buckets.past.slice(0, 4),
  };
}

/** Meetings under their days (the viewer's own calendar days, see timing.ts), in the order given. */
export function groupByDay(meetings: Meeting[]) {
  const groups: { day: Date; meetings: Meeting[] }[] = [];
  for (const meeting of meetings) {
    const day = startOfDay(new Date(meeting.start));
    const last = groups.at(-1);
    if (last && isSameDay(last.day, day)) last.meetings.push(meeting);
    else groups.push({ day, meetings: [meeting] });
  }
  return groups;
}
