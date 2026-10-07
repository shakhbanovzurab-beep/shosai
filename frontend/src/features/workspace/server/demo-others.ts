import type { Project, Team } from "../domain/contract";
import type { KnowledgeItem } from "../domain/knowledge-contract";
import { COLORS, FILES, FIRST, LAST, MEETINGS } from "./demo-names";
import { DAY, minutesAgo, nextMonthStart } from "./demo-people";
import type { BillingStanding, StoredMeeting, StoredMember, StoredTask, WorkspaceData, WorkspaceEvent } from "./types";

/*
 * Other customers' workspaces, so the platform's admin screens have a realistic list. The demo user
 * isn't a member of any, so nothing in the user panel shows them. Everything is generated from a
 * short description of each organisation and is the same on every start.
 */

export type OrgSeed = {
  id: string;
  name: string;
  slug: string;
  domain: string;
  members: number;
  seats: number;
  invites: number;
  /** Days since it was created. */ age: number;
  billing: BillingStanding;
  plan?: { name: string; cents: number };
  suspended?: { days: number; reason: string };
  teams: string[];
  projects: string[];
  /** Average meeting minutes per member this month. */
  minutes: number;
  /** Minutes since anyone was last active. */ quiet: number;
  files: number;
};

const at = (minutes: number) => minutesAgo(Math.max(0, minutes));

function people(org: OrgSeed): StoredMember[] {
  const taken = new Set<string>();
  // Seeded by the address, so each organisation gets its own people.
  const seed = [...org.slug].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return Array.from({ length: org.members }, (_, i) => {
    const first = FIRST[(i * 5 + seed) % FIRST.length] ?? "Alex";
    const last = LAST[(i * 7 + Math.floor(seed / 7)) % LAST.length] ?? "Lee";
    let local = `${first}.${last}`.toLowerCase();
    if (taken.has(local)) local = `${first[0]}.${last}`.toLowerCase();
    taken.add(local);
    let role: StoredMember["role"] = "member";
    if (i === 0) role = "owner";
    else if (i < 3 && org.members > 6) role = "admin";
    return {
      id: `${org.id}-m${i}`,
      account_id: `u-${org.slug}-${i}`,
      name: `${first} ${last}`,
      email: `${local}@${org.domain}`,
      role,
      title: null,
      team_ids: org.teams.length ? [`${org.id}-t${i % org.teams.length}`] : [],
      joined_at: at((org.age - i * 3) * DAY),
      last_active_at: i % 6 === 5 ? null : at(org.quiet + i * 97),
    };
  });
}

const teamsOf = (org: OrgSeed, members: StoredMember[]): Team[] =>
  org.teams.map((name, i) => ({
    id: `${org.id}-t${i}`,
    name,
    description: "",
    color: COLORS[i % COLORS.length] ?? "blue",
    private: false,
    lead_id: members[i + 1]?.id ?? null,
  }));

const projectsOf = (org: OrgSeed, members: StoredMember[]): Project[] =>
  org.projects.map((name, i) => ({
    id: `${org.id}-p${i}`,
    name,
    description: "",
    status: i === 2 ? "completed" : "active",
    lead_id: members[i]?.id ?? null,
    team_id: org.teams.length ? `${org.id}-t${i % org.teams.length}` : null,
    target_date: null,
    created_at: at((org.age - 10 - i) * DAY),
  }));

function meetingsOf(org: OrgSeed, members: StoredMember[]): StoredMeeting[] {
  const count = Math.min(14, Math.round((org.members * org.minutes) / 180));
  return Array.from({ length: count }, (_, i) => {
    const organizer = members[i % members.length] ?? members[0];
    return {
      id: `${org.id}-mt${i}`,
      title: MEETINGS[i % MEETINGS.length] ?? "Sync",
      started_at: at(org.quiet + i * DAY * 2),
      duration_minutes: [30, 45, 60][i % 3] ?? 30,
      owner_account_id: organizer?.account_id ?? "",
      organizer_id: organizer?.id ?? "",
      participants: members.slice(0, 3).map((m) => ({ name: m.name, member_id: m.id })),
      visibility: { level: "workspace", team_id: null },
      project_id: null,
      transcript_shared: false,
      summary: "",
      key_points: [],
      transcript: [],
    };
  });
}

const tasksOf = (org: OrgSeed, members: StoredMember[], meetings: StoredMeeting[]): StoredTask[] =>
  meetings.slice(0, 6).map((meeting, i) => ({
    id: `${org.id}-tk${i}`,
    title: `Follow up on ${meeting.title.toLowerCase()}`,
    status: i % 3 === 0 ? "done" : "todo",
    assignee_id: members[(i + 1) % members.length]?.id ?? null,
    due_on: null,
    project_id: null,
    meeting_id: meeting.id,
    created_at: meeting.started_at,
  }));

const filesOf = (org: OrgSeed, members: StoredMember[]): KnowledgeItem[] =>
  FILES.slice(0, org.files).map((name, i) => ({
    id: `${org.id}-k${i}`,
    name,
    kind: name.endsWith(".xlsx") ? "sheet" : "pdf",
    added_by: members[0]?.id ?? "",
    added_at: at((org.age - 5 - i) * DAY),
    access: { level: "workspace", team_id: null },
    source: { kind: "upload" },
    project_id: null,
    status: "ready",
    size_bytes: 180_000 * (i + 1),
    page_count: null,
  }));

function eventsOf(org: OrgSeed, members: StoredMember[]): WorkspaceEvent[] {
  const owner = members[0]?.name ?? null;
  const ev = (n: number, action: WorkspaceEvent["action"], minutes: number, extra: Partial<WorkspaceEvent> = {}) =>
    ({ id: `${org.id}-ev${n}`, at: at(minutes), action, actor: owner, target: null, value: null, ...extra }) as const;
  const events: WorkspaceEvent[] = [
    ev(0, "workspace_created", org.age * DAY),
    ev(1, "member_invited", (org.age - 1) * DAY, {
      target: members
        .slice(1, 4)
        .map((m) => m.email)
        .join(", "),
    }),
    ev(2, "settings_changed", (org.age - 2) * DAY, { value: "sharing" }),
  ];
  if (members[1]) events.push(ev(3, "role_changed", (org.age - 3) * DAY, { target: members[1].name, value: "admin" }));
  if (org.suspended)
    events.push(ev(4, "suspended", org.suspended.days * DAY, { actor: null, value: org.suspended.reason }));
  return events.toSorted((a, b) => b.at.localeCompare(a.at));
}

/** One generated customer workspace. */
export function orgWorkspace(org: OrgSeed): WorkspaceData {
  const members = people(org);
  const meetings = meetingsOf(org, members);
  return {
    workspace: {
      id: org.id,
      slug: org.slug,
      name: org.name,
      join_domain: org.members > 8 ? org.domain : null,
      sharing: { default_level: "participants", share_transcripts: org.members > 10, members_can_invite: true },
      sharing_reviewed: true,
      plan: {
        name: org.plan?.name ?? "Team",
        seats: org.seats,
        price_per_seat_cents: org.plan?.cents ?? 2000,
        currency: "USD",
        renews_at: nextMonthStart(),
      },
      created_at: at(org.age * DAY),
    },
    members,
    invitations: Array.from({ length: org.invites }, (_, i) => ({
      id: `${org.id}-inv${i}`,
      email: `new.hire${i + 1}@${org.domain}`,
      role: "member",
      team_ids: [],
      invited_by: members[0]?.id ?? "",
      sent_at: at((i + 1) * DAY),
    })),
    teams: teamsOf(org, members),
    projects: projectsOf(org, members),
    meetings,
    decisions: [],
    tasks: tasksOf(org, members, meetings),
    knowledge: filesOf(org, members),
    usage: Object.fromEntries(
      members.map((m, i) => [m.id, [Math.round(org.minutes / 40) + (i % 3), org.minutes + ((i * 37) % 90)]]),
    ),
    control: {
      suspended: org.suspended ? { at: at(org.suspended.days * DAY), reason: org.suspended.reason } : null,
      billing: org.billing,
      trial_ends_at:
        org.billing === "trialing" ? new Date(Date.now() + (14 - org.age) * 86_400_000).toISOString() : null,
      events: eventsOf(org, members),
    },
  };
}
