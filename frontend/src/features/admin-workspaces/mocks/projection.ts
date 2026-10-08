import { seatsUsed } from "@/features/workspace/mocks/events";
import type { WorkspaceData } from "@/features/workspace/mocks/types";

import type { AdminMember, AdminWorkspace, AdminWorkspaceDetail } from "../domain/contract";

/*
 * What the platform's team sees of a workspace: who runs it, what it pays, how much it is used and
 * what happened in it. Counts only: meeting notes, file contents and task titles never leave here.
 */

const latest = (dates: (string | null)[]) =>
  dates.reduce<string | null>((max, d) => (d !== null && (max === null || d > max) ? d : max), null);

export function toRow(data: WorkspaceData): AdminWorkspace {
  const { workspace, members, control } = data;
  const owner = members.find((m) => m.role === "owner");
  const usage = Object.values(data.usage);
  return {
    id: workspace.id,
    name: workspace.name,
    slug: workspace.slug,
    owner: owner ? { name: owner.name, email: owner.email } : null,
    plan: { ...workspace.plan },
    status: control.suspended ? "suspended" : control.billing,
    trial_ends_at: control.trial_ends_at,
    members: members.length,
    pending_invitations: data.invitations.length,
    seats_used: seatsUsed(data),
    monthly_cents: workspace.plan.seats * workspace.plan.price_per_seat_cents,
    meetings_month: usage.reduce((sum, [meetings]) => sum + meetings, 0),
    minutes_month: usage.reduce((sum, [, minutes]) => sum + minutes, 0),
    last_active_at: latest(members.map((m) => m.last_active_at)),
    created_at: workspace.created_at,
  };
}

function people(data: WorkspaceData): AdminMember[] {
  const order = { owner: 0, admin: 1, member: 2 } as const;
  return data.members
    .map((m) => {
      const [meetings, minutes] = data.usage[m.id] ?? [0, 0];
      return {
        id: m.id,
        name: m.name,
        email: m.email,
        role: m.role,
        teams: m.team_ids.length,
        meetings_month: meetings,
        minutes_month: minutes,
        joined_at: m.joined_at,
        last_active_at: m.last_active_at,
      };
    })
    .toSorted((a, b) => order[a.role] - order[b.role] || a.name.localeCompare(b.name));
}

export function toDetail(data: WorkspaceData): AdminWorkspaceDetail {
  const sources = data.knowledge.filter((k) => k.source.kind === "connector");
  return {
    ...toRow(data),
    join_domain: data.workspace.join_domain,
    sharing: { ...data.workspace.sharing },
    suspension: data.control.suspended,
    people: people(data),
    invitations: data.invitations.map((i) => ({ email: i.email, role: i.role, sent_at: i.sent_at })),
    teams: data.teams.map((t) => ({
      id: t.id,
      name: t.name,
      private: t.private,
      members: data.members.filter((m) => m.team_ids.includes(t.id)).length,
    })),
    content: {
      shared_meetings: data.meetings.length,
      decisions: data.decisions.length,
      open_tasks: data.tasks.filter((t) => t.status !== "done").length,
      projects: data.projects.length,
      active_projects: data.projects.filter((p) => p.status === "active").length,
      files: data.knowledge.length - sources.length,
      sources: sources.length,
      knowledge_bytes: data.knowledge.reduce((sum, k) => sum + (k.size_bytes ?? 0), 0),
    },
    events: data.control.events.map((e) => ({ ...e })),
  };
}
