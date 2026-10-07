import type { Project, Workspace } from "../domain/contract";
import { DAY, dayFromNow, HOUR, minutesAgo, nextMonthStart, PEOPLE, TEAM_SEAT_CENTS } from "./demo-people";
import { action } from "./demo-rows";
import type { MeetingSeed, StoredMember } from "./types";

/*
 * Northwind pilot: a customer's workspace for running the Leo pilot together. The demo user is a
 * member here, not an admin, and members can't invite: it shows how the product reads without control.
 */

export const NORTHWIND = "ws-northwind";

export const northwindWorkspace = (): Workspace => ({
  id: NORTHWIND,
  slug: "northwind",
  name: "Northwind pilot",
  join_domain: "northwind.com",
  sharing: { default_level: "participants", share_transcripts: false, members_can_invite: false },
  sharing_reviewed: true,
  plan: { name: "Team", seats: 6, price_per_seat_cents: TEAM_SEAT_CENTS, currency: "USD", renews_at: nextMonthStart() },
  created_at: "2026-09-21T09:00:00.000Z",
});

type Seat = [id: string, name: string, title: string, role: StoredMember["role"], activeMinutesAgo: number];

const SEATS: Seat[] = [
  ["nw-liam", "Liam Turner", "Head of Operations, Northwind", "owner", 2 * HOUR],
  ["nw-grace", "Grace Ito", "IT lead, Northwind", "admin", 6 * HOUR],
  ["nw-arham", "Arham Khan", "Product lead, Lumen", "member", 0],
  ["nw-priya", "Priya Nair", "Data analyst, Lumen", "member", DAY],
];

export const northwindMembers = (): StoredMember[] =>
  SEATS.map(([id, name, title, role, active], index) => {
    const person = PEOPLE[name];
    return {
      id,
      account_id: person?.account ?? id,
      name,
      email: person?.email ?? `${id}@northwind.com`,
      role,
      title,
      team_ids: [],
      joined_at: new Date(Date.UTC(2026, 8, 21 + index)).toISOString(),
      last_active_at: minutesAgo(active),
    };
  });

export const northwindProjects = (): Project[] => [
  {
    id: "pilot",
    name: "Pilot rollout",
    // i18n-ignore: demo data, a project description its lead wrote
    description: "Thirty people in Northwind operations using Leo for every internal meeting.",
    status: "active",
    lead_id: "nw-liam",
    team_id: null,
    target_date: dayFromNow(21),
    created_at: "2026-09-21T09:00:00.000Z",
  },
];

export const northwindMeetings: MeetingSeed[] = [
  {
    id: "northwind-pilot-kickoff",
    // i18n-ignore: demo data, a meeting title its organizer wrote
    title: "Pilot kickoff",
    started_at: "2026-10-01T15:00:00Z",
    duration_minutes: 45,
    owner: "Liam Turner",
    participants: ["Liam Turner", "Grace Ito", "Arham Khan", "Priya Nair"],
    visibility: { level: "workspace", team_id: null },
    project_id: "pilot",
    transcript_shared: false,
    summary:
      "Northwind starts with its operations team of thirty. Grace needs the admin guide for IT review before accounts are created; success is measured on decisions captured and follow-ups sent.",
    key_points: ["IT reviews data handling before rollout.", "Weekly check-ins every Thursday."],
    decisions: ["Start the pilot with the operations team (30 people)."],
    actions: [
      action("Share the admin guide with Northwind IT", "Arham Khan", "todo", 2),
      action("Collect the list of pilot users", "Grace Ito", "todo", 1),
      action("Set up the SSO test tenant", "Liam Turner", "done", -2),
    ],
    transcript: [],
  },
  {
    id: "northwind-checkin-1",
    // i18n-ignore: demo data, a meeting title its organizer wrote
    title: "Weekly pilot check-in",
    started_at: "2026-10-02T16:00:00Z",
    duration_minutes: 25,
    owner: "Liam Turner",
    participants: ["Liam Turner", "Arham Khan"],
    visibility: { level: "participants", team_id: null },
    project_id: "pilot",
    transcript_shared: false,
    summary: "First week went smoothly. Liam wants a short weekly usage summary to share with his managers.",
    key_points: ["Twelve people recorded meetings in the first week."],
    decisions: [],
    actions: [action("Send the weekly usage summary", "Arham Khan", "in_progress", 4)],
    transcript: [],
  },
];

export const NORTHWIND_USAGE: Record<string, [number, number]> = {
  "nw-liam": [6, 210],
  "nw-grace": [3, 95],
  "nw-arham": [2, 70],
  "nw-priya": [1, 25],
};
