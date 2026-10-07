import type { Visibility } from "../domain/content-contract";
import type { Invitation, Project, Team, Workspace } from "../domain/contract";
import { DAY, dayFromNow, HOUR, minutesAgo, nextMonthStart, PEOPLE, TEAM_SEAT_CENTS } from "./demo-people";
import type { StoredMember } from "./types";

/* Lumen: the company building Leo, owned by the demo user. Times are relative to the server start. */

export const LUMEN = "ws-lumen";

export const lumenWorkspace = (): Workspace => ({
  id: LUMEN,
  slug: "lumen",
  name: "Lumen",
  join_domain: "lumen.so",
  sharing: { default_level: "participants", share_transcripts: true, members_can_invite: true },
  sharing_reviewed: true,
  plan: {
    name: "Team",
    seats: 10,
    price_per_seat_cents: TEAM_SEAT_CENTS,
    currency: "USD",
    renews_at: nextMonthStart(),
  },
  created_at: "2025-11-03T09:00:00.000Z",
});

const team = (id: string, name: string, description: string, color: Team["color"], lead: string, priv = false) =>
  ({ id, name, description, color, private: priv, lead_id: lead }) satisfies Team;

export const lumenTeams = (): Team[] => [
  team("product", "Product", "Roadmap, research and design.", "violet", "m-arham"),
  team("engineering", "Engineering", "Building and running Leo.", "blue", "m-maya"),
  team("sales", "Sales", "Pipeline, customers and pricing.", "amber", "m-elena"),
  team("leadership", "Leadership", "Hiring, budget and strategy.", "rose", "m-arham", true),
];

type Seat = [
  id: string,
  name: string,
  title: string,
  role: StoredMember["role"],
  teams: string[],
  activeMinutesAgo: number,
];

const SEATS: Seat[] = [
  ["m-arham", "Arham Khan", "Product lead", "owner", ["product", "engineering", "leadership"], 0],
  ["m-maya", "Maya Chen", "Engineering manager", "admin", ["engineering", "leadership"], HOUR],
  ["m-elena", "Elena Petrova", "Head of Sales", "admin", ["sales", "leadership"], 5 * HOUR],
  ["m-diego", "Diego Alvarez", "Designer", "member", ["product"], 3 * HOUR],
  ["m-priya", "Priya Nair", "Data analyst", "member", ["product", "sales"], DAY + 2 * HOUR],
  ["m-noah", "Noah Kim", "Backend engineer", "member", ["engineering"], 20],
  ["m-sofia", "Sofia Rossi", "Frontend engineer", "member", ["engineering"], 2 * DAY],
  ["m-tom", "Tom Becker", "Account executive", "member", ["sales"], 41 * DAY],
];

export const lumenMembers = (): StoredMember[] =>
  SEATS.map(([id, name, title, role, team_ids, active], index) => {
    const person = PEOPLE[name];
    return {
      id,
      account_id: person?.account ?? id,
      name,
      email: person?.email ?? `${id}@lumen.so`,
      role,
      title,
      team_ids,
      joined_at: new Date(Date.UTC(2025, 10, 3 + index * 9)).toISOString(),
      last_active_at: minutesAgo(active),
    };
  });

export const lumenInvitations = (): Invitation[] => [
  {
    id: "inv-lucas",
    email: "lucas@lumen.so",
    role: "member",
    team_ids: ["engineering"],
    invited_by: "m-maya",
    sent_at: minutesAgo(2 * DAY + 3 * HOUR),
  },
];

const project = (
  id: string,
  name: string,
  description: string,
  lead: string,
  team_id: string | null,
  target: number | null,
  status: Project["status"] = "active",
): Project => ({
  id,
  name,
  description,
  status,
  lead_id: lead,
  team_id,
  target_date: target === null ? null : dayFromNow(target),
  created_at: "2026-09-01T09:00:00.000Z",
});

export const lumenProjects = (): Project[] => [
  project(
    "leo-beta",
    "Leo beta launch",
    "Open the Leo agent to 50 customers behind a feature flag.",
    "m-arham",
    "product",
    41,
  ),
  project(
    "pricing",
    "Team plan pricing",
    "Seat pricing with an agent-minutes add-on, and the pricing page.",
    "m-elena",
    "sales",
    24,
  ),
  project(
    "onboarding",
    "Onboarding redesign",
    "A first run that shows value before any setup.",
    "m-diego",
    "product",
    30,
  ),
  project("hiring", "Q4 hiring", "Two engineers and an account executive.", "m-maya", "leadership", 70),
  project(
    "reliability",
    "Stream reliability",
    "No dropped answers: heartbeats, alerts and retries.",
    "m-noah",
    "engineering",
    null,
    "completed",
  ),
];

const audience = (level: Visibility["level"], team_id: string | null = null): Visibility => ({ level, team_id });

/** Which of the demo user's recordings are shared into Lumen, with whom and for which project. */
export const LUMEN_SHARES: Record<string, { visibility: Visibility; project: string | null; transcript: boolean }> = {
  "q4-roadmap-review": { visibility: audience("workspace"), project: "leo-beta", transcript: true },
  "leo-design-critique": { visibility: audience("team", "product"), project: "leo-beta", transcript: true },
  "pricing-workshop": { visibility: audience("team", "sales"), project: "pricing", transcript: true },
  "customer-interview-northwind": { visibility: audience("team", "product"), project: "onboarding", transcript: false },
  "weekly-engineering-sync": { visibility: audience("team", "engineering"), project: "reliability", transcript: true },
  "standup-sep-29": { visibility: audience("team", "engineering"), project: "leo-beta", transcript: true },
};

/** Meetings and minutes recorded this month, per member. */
export const LUMEN_USAGE: Record<string, [number, number]> = {
  "m-arham": [14, 520],
  "m-maya": [18, 610],
  "m-elena": [16, 700],
  "m-diego": [9, 280],
  "m-priya": [11, 390],
  "m-noah": [7, 190],
  "m-sofia": [8, 230],
};
