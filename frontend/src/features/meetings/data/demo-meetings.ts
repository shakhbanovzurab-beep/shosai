import { addDays, addMinutes, setHours, setMinutes, startOfDay } from "date-fns";

import type { Meeting, MeetingSource } from "../domain/meeting";

/*
 * Sample scheduled meetings until the meetings API exists: one in progress and the next few days.
 * Times are relative to now, so the page always has something live and something ahead. Past
 * meetings come from the recordings in Notes (see model/meetings-resource.ts). Titles, people and
 * rooms are what the organisers wrote, so they stay as written in every interface language.
 */

const people = (...names: string[]) => names.map((name) => ({ name }));

const at = (base: Date, dayOffset: number, hour: number, minute = 0) =>
  setMinutes(setHours(addDays(startOfDay(base), dayOffset), hour), minute);

type Draft = Omit<Meeting, "start" | "end" | "recap" | "location"> & {
  start: Date;
  minutes: number;
  location?: string;
};

/** A demo meeting: its id and title, then when, where and with whom. */
const draft = (id: string, title: string, fields: Omit<Draft, "id" | "title">): Draft => ({ id, title, ...fields });

const scheduled = (now: Date): Draft[] => {
  // Started a quarter of an hour ago, so it is live whenever the page opens.
  const liveStart = addMinutes(now, -18);
  return [
    draft("m-product-sync", "Product sync — Leo beta", {
      start: liveStart,
      minutes: 45,
      source: "google_meet",
      joinUrl: "https://meet.google.com/whr-leob-eta",
      participants: people("Maya Chen", "Diego Alvarez", "Priya Nair", "Noah Kim", "Arham Khan"),
    }),
    draft("m-design-review", "Design review: Meetings page", {
      start: addMinutes(liveStart, 90),
      minutes: 30,
      source: "zoom",
      joinUrl: "https://zoom.us/j/84213370042",
      participants: people("Maya Chen", "Arham Khan", "Sofia Rossi"),
    }),
    draft("m-candidate", "Interview: Senior frontend engineer", {
      start: addMinutes(liveStart, 240),
      minutes: 60,
      source: "shosai",
      joinUrl: "https://shosai.tech/room/fe-interview-7q2",
      participants: people("Noah Kim", "Arham Khan", "Elena Petrova"),
    }),
    draft("m-sprint-planning", "Sprint planning", {
      start: at(now, 1, 9, 30),
      minutes: 90,
      source: "teams",
      joinUrl: "https://teams.microsoft.com/l/meetup-join/sprint-planning",
      participants: people(
        "Noah Kim",
        "Diego Alvarez",
        "Priya Nair",
        "Maya Chen",
        "Arham Khan",
        "Sofia Rossi",
        "Liam Turner",
      ),
    }),
    draft("m-acme", "Customer call — Acme", {
      start: at(now, 2, 15),
      minutes: 45,
      source: "zoom",
      joinUrl: "https://zoom.us/j/99120045811",
      participants: people("Priya Nair", "Jordan Lee"),
    }),
    draft("m-board", "Quarterly board update", {
      start: at(now, 3, 11),
      minutes: 60,
      source: "in_person",
      joinUrl: null,
      location: "Office, room 4",
      participants: people("Arham Khan", "Elena Petrova", "Marcus Webb"),
    }),
  ];
};

export function demoMeetings(now = new Date()): Meeting[] {
  return scheduled(now).map(({ start, minutes, location, ...meeting }) => ({
    ...meeting,
    start: start.toISOString(),
    end: addMinutes(start, minutes).toISOString(),
    location: location ?? null,
    recap: null,
  }));
}

/** Where each recorded meeting in Notes took place; Shosai captured them on the user's device either way. */
export const NOTE_SOURCES: Record<string, MeetingSource> = {
  "customer-interview-northwind": "zoom",
  "weekly-engineering-sync": "google_meet",
  "one-on-one-maya": "shosai",
  "pricing-workshop": "in_person",
};
