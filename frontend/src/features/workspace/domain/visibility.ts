import type { MeetingParticipant, Visibility } from "./content-contract";
import type { Member, Team } from "./contract";
import type { KnowledgeAccess } from "./knowledge-contract";

type Shareable = { organizer_id: string; participants: MeetingParticipant[]; visibility: Visibility };

/** The access rule the API applies: the organizer, the members who took part, the team, or everyone. */
export function canSee(member: Pick<Member, "id" | "team_ids">, meeting: Shareable) {
  const { level, team_id } = meeting.visibility;
  if (meeting.organizer_id === member.id || level === "workspace") return true;
  if (meeting.participants.some((p) => p.member_id === member.id)) return true;
  return level === "team" && team_id !== null && member.team_ids.includes(team_id);
}

/** A Select value for a visibility: "participants", "workspace" or "team:<id>". */
export const visibilityKey = (v: Visibility) => (v.level === "team" ? `team:${v.team_id}` : v.level);

export function parseVisibilityKey(key: string): Visibility {
  if (key.startsWith("team:")) return { level: "team", team_id: key.slice(5) };
  return { level: key === "workspace" ? "workspace" : "participants", team_id: null };
}

/** The audiences of a share menu, narrowest first; teams the member isn't in show only to admins. */
export function shareAudiences(teams: Team[], me: Pick<Member, "team_ids">, admin: boolean): Visibility[] {
  const mine = new Set(me.team_ids);
  return [
    { level: "participants", team_id: null },
    ...teams.filter((t) => admin || mine.has(t.id)).map((t): Visibility => ({ level: "team", team_id: t.id })),
    { level: "workspace", team_id: null },
  ];
}

/* ---------- Knowledge: for everyone, or for one team ---------- */

export const accessKey = (access: KnowledgeAccess) =>
  access.level === "team" ? `team:${access.team_id}` : "workspace";

export const parseAccessKey = (key: string): KnowledgeAccess =>
  key.startsWith("team:") ? { level: "team", team_id: key.slice(5) } : { level: "workspace", team_id: null };

/** Everyone first, then the teams the member is in (every team for admins). */
export function accessAudiences(teams: Team[], me: Pick<Member, "team_ids">, admin: boolean): KnowledgeAccess[] {
  const mine = new Set(me.team_ids);
  return [
    { level: "workspace", team_id: null },
    ...teams.filter((t) => admin || mine.has(t.id)).map((t): KnowledgeAccess => ({ level: "team", team_id: t.id })),
  ];
}

/** Knowledge for everyone, or for a team the member is in; admins see all of it, and so does who added it. */
export const canUseKnowledge = (
  member: Pick<Member, "id" | "team_ids">,
  admin: boolean,
  item: { access: KnowledgeAccess; added_by: string },
) =>
  item.access.level === "workspace" ||
  admin ||
  item.added_by === member.id ||
  (item.access.team_id !== null && member.team_ids.includes(item.access.team_id));
