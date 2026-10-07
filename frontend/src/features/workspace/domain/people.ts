import type { Member, WorkspaceState } from "./contract";

/** Seats paid for, and how many members and pending invitations take. */
export function seatUsage(state: WorkspaceState) {
  const taken = state.members.length + state.invitations.length;
  const total = state.workspace.plan.seats;
  return { total, members: state.members.length, pending: state.invitations.length, left: Math.max(0, total - taken) };
}

const EMAIL = /^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+$/;

export type ParsedInvites = { emails: string[]; invalid: string[]; existing: string[] };

/**
 * Emails pasted into the invite box, separated by commas, semicolons, spaces or new lines. Duplicates
 * collapse; addresses already in the workspace or invited are set aside instead of failing the batch.
 */
export function parseInviteEmails(text: string, state: WorkspaceState): ParsedInvites {
  const taken = new Set([
    ...state.members.map((m) => m.email.toLowerCase()),
    ...state.invitations.map((i) => i.email.toLowerCase()),
  ]);
  const seen = new Set<string>();
  const emails: string[] = [];
  const invalid: string[] = [];
  const existing: string[] = [];
  for (const raw of text.split(/[\s,;]+/)) {
    const email = raw.trim().replace(/^<|>$/g, "").toLowerCase();
    if (!email || seen.has(email)) continue;
    seen.add(email);
    if (!EMAIL.test(email)) invalid.push(raw.trim());
    else if (taken.has(email)) existing.push(email);
    else emails.push(email);
  }
  return { emails, invalid, existing };
}

/** Free-mail domains never become a workspace's join domain. */
const PUBLIC_DOMAINS = new Set([
  "gmail.com",
  "googlemail.com",
  "outlook.com",
  "hotmail.com",
  "yahoo.com",
  "icloud.com",
]);

/** The domain to suggest for joining without an invite: the owner's work email domain, if it is one. */
export function suggestedJoinDomain(owner: Member | undefined) {
  const domain = owner?.email.split("@")[1]?.toLowerCase();
  return domain && !PUBLIC_DOMAINS.has(domain) ? domain : null;
}

const DOMAIN = /^(?=.{3,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$/;

export const isDomain = (value: string) => DOMAIN.test(value) && !PUBLIC_DOMAINS.has(value);

/** Members of a team, its lead first, then by name. */
export function teamMembers(state: WorkspaceState, teamId: string) {
  const lead = state.teams.find((t) => t.id === teamId)?.lead_id;
  return state.members
    .filter((m) => m.team_ids.includes(teamId))
    .sort((a, b) => Number(b.id === lead) - Number(a.id === lead) || a.name.localeCompare(b.name));
}

/** Teams a member can see: open ones, private ones they belong to, all of them for admins. */
export function visibleTeams(state: WorkspaceState, me: Member, admin: boolean) {
  const mine = new Set(me.team_ids);
  return state.teams.filter((t) => !t.private || admin || mine.has(t.id));
}

export const memberById = (state: WorkspaceState) => new Map(state.members.map((m) => [m.id, m]));

/** "Arham" from "Arham Khan". */
export const firstName = (name: string) => name.split(" ")[0] ?? name;
