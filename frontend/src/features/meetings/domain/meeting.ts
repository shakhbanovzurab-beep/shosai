import { differenceInMinutes } from "date-fns";

import { dayIn } from "@/i18n/calendar-days";

/* A meeting as the Meetings page sees it: scheduled, in progress or over, wherever it takes place. */

// `recording` и `upload` — записи «Заметок»: сделанная в приложении и загруженная файлом; площадка звонка у них неизвестна.
export const MEETING_SOURCES = ["google_meet", "zoom", "teams", "shosai", "in_person", "recording", "upload"] as const;
export type MeetingSource = (typeof MEETING_SOURCES)[number];

/** What Leo made of a recorded meeting; the full notes live in Notes. `decisions` is null when not counted. */
export type MeetingRecap = { noteId: string; summary: string; tasks: number; decisions: number | null };

/** Запись встречи в «Заметках»: её страница, идёт ли она сейчас и меняется ли ещё (идёт или пишутся заметки). */
export type MeetingRecording = { noteId: string; live: boolean; busy: boolean };

export type Meeting = {
  id: string;
  title: string;
  /** ISO timestamps. */
  start: string;
  end: string;
  source: MeetingSource;
  /** The call's link; null for a meeting in person. A Shosai room opens the LiveKit Meeting Room. */
  joinUrl: string | null;
  location: string | null;
  participants: { name: string }[];
  /** Null until the meeting has been recorded and summarized. */
  recap: MeetingRecap | null;
  /** Null for a meeting that has no recording in Notes. */
  recording: MeetingRecording | null;
  /** Звонок своей комнаты Shosai: идёт, пока не закончится; конца по плану у него нет. */
  endless?: boolean;
};

export type MeetingStatus = "live" | "upcoming" | "past";

export function meetingStatus(meeting: Meeting, now: number): MeetingStatus {
  // Запись идёт, пока её не закончили, сколько бы она ни длилась; конец законченной уже прошёл.
  if (meeting.recording) return meeting.recording.live ? "live" : "past";
  if (meeting.endless) return "live";
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
export function overviewSections(buckets: MeetingBuckets, now: number, zone: string) {
  const today = dayIn(now, zone);
  // Дни-строки «2026-10-20» сравниваются по порядку как текст.
  const laterToday = buckets.upcoming.filter((m) => dayIn(m.start, zone) === today);
  return {
    live: buckets.live,
    laterToday,
    upcoming: buckets.upcoming.filter((m) => dayIn(m.start, zone) > today).slice(0, 4),
    recent: buckets.past.slice(0, 4),
  };
}

/** Встречи под их днями (календарные дни пояса кабинета, см. timing.ts), в данном порядке. */
export function groupByDay(meetings: Meeting[], zone: string) {
  const groups: { day: string; meetings: Meeting[] }[] = [];
  for (const meeting of meetings) {
    const day = dayIn(meeting.start, zone);
    const last = groups.at(-1);
    if (last && last.day === day) last.meetings.push(meeting);
    else groups.push({ day, meetings: [meeting] });
  }
  return groups;
}
