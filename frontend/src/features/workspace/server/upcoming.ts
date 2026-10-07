import type { UpcomingMeeting, Visibility } from "../domain/content-contract";
import type { Member } from "../domain/contract";
import { LUMEN } from "./demo-lumen";
import { NORTHWIND } from "./demo-northwind";
import type { WorkspaceData } from "./types";

/* Meetings coming up in each workspace, relative to now, and where their notes will go. */

const MINUTE = 60_000;
const at = (minutesFromNow: number) => new Date(Date.now() + minutesFromNow * MINUTE).toISOString();

type Seed = [id: string, title: string, start: number, minutes: number, people: string[], team: string | null];

/** Lumen follows the same schedule as the Meetings page: one in progress, two later today, one tomorrow. */
const SCHEDULE: Record<string, Seed[]> = {
  [LUMEN]: [
    [
      "m-product-sync",
      "Product sync — Leo beta",
      -18,
      45,
      ["Maya Chen", "Diego Alvarez", "Priya Nair", "Noah Kim", "Arham Khan"],
      "product",
    ],
    ["m-design-review", "Design review: Meetings page", 72, 30, ["Maya Chen", "Arham Khan", "Sofia Rossi"], null],
    ["m-candidate", "Interview: Senior frontend engineer", 222, 60, ["Noah Kim", "Arham Khan", "Jamie Fox"], null],
    [
      "m-sprint-planning",
      "Sprint planning",
      20 * 60,
      90,
      ["Noah Kim", "Diego Alvarez", "Maya Chen", "Arham Khan", "Sofia Rossi"],
      "engineering",
    ],
  ],
  [NORTHWIND]: [["nw-checkin-2", "Weekly pilot check-in", 2 * 24 * 60, 25, ["Liam Turner", "Arham Khan"], null]],
};

/** The member's upcoming meetings here; guests keep a meeting's notes with its organizer. */
export function listUpcoming(data: WorkspaceData, viewer: Member): UpcomingMeeting[] {
  const byName = new Map(data.members.map((m) => [m.name, m]));
  const seeds = SCHEDULE[data.workspace.id] ?? [];
  return seeds.flatMap(([id, title, start, minutes, people, team]) => {
    const participants = people.map((name) => ({ name, member_id: byName.get(name)?.id ?? null }));
    if (!participants.some((p) => p.member_id === viewer.id)) return [];
    const external = participants.some((p) => p.member_id === null);
    let shares_with: Visibility | null = null;
    if (!external && team && data.teams.some((t) => t.id === team)) shares_with = { level: "team", team_id: team };
    else if (!external && data.workspace.sharing.default_level !== "private")
      shares_with = { level: data.workspace.sharing.default_level, team_id: null };
    return [{ id, title, start: at(start), end: at(start + minutes), participants, external, shares_with }];
  });
}
