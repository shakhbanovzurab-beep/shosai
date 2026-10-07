import type { WorkspaceState, WorkspaceSummary } from "../domain/contract";
import { advanceIndexing } from "./demo-knowledge";
import { LUMEN } from "./demo-lumen";
import { NORTHWIND } from "./demo-northwind";
import { otherWorkspaces } from "./demo-others-seed";
import { ME, ME_ACCOUNT, minutesAgo, nextMonthStart, TEAM_SEAT_CENTS } from "./demo-people";
import { seededLumen, seededNorthwind } from "./demo-seeds";
import type { StoredMember, WorkspaceData } from "./types";

/*
 * In-memory workspaces for the demo, used when BACKEND_API_URL is unset; resets on restart. The
 * signed-in account is always the demo user: owner of Lumen, member of the Northwind pilot.
 */

const shared = globalThis as typeof globalThis & { workspaceDemo?: Map<string, WorkspaceData> };
shared.workspaceDemo ??= new Map([
  [LUMEN, seededLumen()],
  [NORTHWIND, seededNorthwind()],
  ...otherWorkspaces().map((data) => [data.workspace.id, data] as const),
]);
const workspaces = shared.workspaceDemo;

/** Every workspace in the demo, including ones the account isn't in (for cross-workspace housekeeping). */
export const everyWorkspace = () => [...workspaces.values()];

/** The signed-in account's member in a workspace, or null when it isn't one. */
export const meIn = (data: WorkspaceData) => data.members.find((m) => m.account_id === ME_ACCOUNT) ?? null;

/** The workspaces the account is a member of, oldest first, including suspended ones. */
export const myWorkspaces = () => [...workspaces.values()].filter((data) => meIn(data) !== null);

/** The account's workspaces it can use now: what Personal shows and Leo reads. Suspended ones are left out. */
export const activeWorkspaces = () => myWorkspaces().filter((data) => data.control.suspended === null);

/** A workspace the account is in, with its member there; null otherwise (not found looks the same). */
export function membership(id: string) {
  const data = workspaces.get(id);
  const me = data ? meIn(data) : null;
  return data && me ? { data, me } : null;
}

/** The same, for work done from Personal (Kanban, Leo): a suspended workspace counts as unavailable. */
export function activeMembership(id: string) {
  const found = membership(id);
  return found && found.data.control.suspended === null ? found : null;
}

const publicMember = ({ account_id: _account, ...member }: StoredMember) => member;

export function stateOf(data: WorkspaceData, me: StoredMember): WorkspaceState {
  advanceIndexing(data.knowledge);
  return {
    workspace: data.workspace,
    me_id: me.id,
    members: data.members.map(publicMember),
    invitations: data.invitations,
    teams: data.teams,
    projects: data.projects,
  };
}

export const summaryOf = (data: WorkspaceData, me: StoredMember): WorkspaceSummary => ({
  id: data.workspace.id,
  slug: data.workspace.slug,
  name: data.workspace.name,
  role: me.role,
  member_count: data.members.length,
  suspended: data.control.suspended !== null,
});

const slugify = (name: string) =>
  name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 40) || "workspace";

/** A new workspace with the account as its only member and the recommended sharing rules to confirm. */
export function createWorkspace(name: string, seats: number) {
  const taken = new Set([...workspaces.values()].map((d) => d.workspace.slug));
  let slug = slugify(name);
  for (let n = 2; taken.has(slug) || slug === "new"; n++) slug = `${slugify(name)}-${n}`;
  const id = `ws-${crypto.randomUUID().slice(0, 8)}`;
  const founder: StoredMember = {
    id: `${id}-arham`,
    account_id: ME_ACCOUNT,
    name: ME.name,
    email: ME.email,
    role: "owner",
    title: null,
    team_ids: [],
    joined_at: new Date().toISOString(),
    last_active_at: minutesAgo(0),
  };
  const data: WorkspaceData = {
    workspace: {
      id,
      slug,
      name,
      join_domain: null,
      sharing: { default_level: "participants", share_transcripts: false, members_can_invite: true },
      sharing_reviewed: false,
      plan: {
        name: "Team",
        seats,
        price_per_seat_cents: TEAM_SEAT_CENTS,
        currency: "USD",
        renews_at: nextMonthStart(),
      },
      created_at: new Date().toISOString(),
    },
    members: [founder],
    invitations: [],
    teams: [],
    projects: [],
    meetings: [],
    decisions: [],
    tasks: [],
    knowledge: [],
    usage: {},
    control: {
      suspended: null,
      billing: "trialing",
      trial_ends_at: new Date(Date.now() + 14 * 86_400_000).toISOString(),
      events: [
        {
          id: `ev-${crypto.randomUUID().slice(0, 8)}`,
          at: new Date().toISOString(),
          action: "workspace_created",
          actor: ME.name,
          target: null,
          value: null,
        },
      ],
    },
  };
  workspaces.set(id, data);
  return { data, me: founder };
}

export const deleteWorkspace = (id: string) => workspaces.delete(id);

export const memberName = (data: WorkspaceData, id: string | null) =>
  data.members.find((m) => m.id === id)?.name ?? null;
