import { JsonResponse } from "@/mocks/runtime";

import type { TeamInput, WorkspaceState } from "../domain/contract";
import { isAdmin } from "../domain/roles";
import { stateOf } from "./demo-store";
import { type Ctx, type Found, type ItemCtx, inWorkspace, item } from "./guards";
import { refuse } from "./problems";
import { firstIssue, readJson, teamInputSchema } from "./schemas";

/* Teams inside a workspace (groups here, to keep them apart from the workspace itself). */

const slug = (name: string) =>
  name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 32) || "team";

/** Puts exactly the given members in the team. */
function setMembers({ data }: Found, teamId: string, memberIds: string[]) {
  const wanted = new Set(memberIds);
  for (const member of data.members) {
    const inTeam = member.team_ids.includes(teamId);
    if (wanted.has(member.id) && !inTeam) member.team_ids = [...member.team_ids, teamId];
    if (!wanted.has(member.id) && inTeam) member.team_ids = member.team_ids.filter((t) => t !== teamId);
  }
}

async function parse(request: Request, { data }: Found): Promise<TeamInput | Response> {
  const body = teamInputSchema.safeParse(await readJson(request));
  if (!body.success) return refuse(firstIssue(body.error), 422);
  if (!body.data.member_ids.every((id) => data.members.some((m) => m.id === id))) return refuse("peopleGone", 422);
  return body.data;
}

const ok = ({ data, me }: Found, status = 200) => JsonResponse.json<WorkspaceState>(stateOf(data, me), { status });

/** /api/workspaces/[ws]/teams */
export const groupsRoute = {
  POST: (request: Request, { params }: Ctx) =>
    inWorkspace(
      request,
      params,
      () => "/teams",
      async (found) => {
        if (!isAdmin(found.me)) return refuse("adminsCreateTeams", 403);
        const input = await parse(request, found);
        if (input instanceof Response) return input;
        const { data, me } = found;
        if (data.teams.some((t) => t.name.toLowerCase() === input.name.toLowerCase()))
          return refuse((t) => t("teamNameTaken", { name: input.name }), 409);
        let id = slug(input.name);
        while (data.teams.some((t) => t.id === id)) id = `${id}-2`;
        const { member_ids, ...fields } = input;
        data.teams.push({ id, ...fields, lead_id: member_ids.includes(me.id) ? me.id : (member_ids[0] ?? null) });
        setMembers(found, id, member_ids);
        return ok(found, 201);
      },
    ),
};

/** /api/workspaces/[ws]/teams/[id] */
export const groupRoute = {
  PATCH: (request: Request, { params }: ItemCtx) =>
    inWorkspace(request, params, item("/teams"), async (found, { id }) => {
      if (!isAdmin(found.me)) return refuse("adminsEditTeams", 403);
      const team = found.data.teams.find((t) => t.id === id);
      if (!team) return refuse("teamGone", 404);
      const input = await parse(request, found);
      if (input instanceof Response) return input;
      if (found.data.teams.some((t) => t.id !== id && t.name.toLowerCase() === input.name.toLowerCase()))
        return refuse((t) => t("teamNameTaken", { name: input.name }), 409);
      const { member_ids, ...fields } = input;
      Object.assign(team, fields);
      if (!team.lead_id || !member_ids.includes(team.lead_id)) team.lead_id = member_ids[0] ?? null;
      setMembers(found, id, member_ids);
      return ok(found);
    }),

  DELETE: (request: Request, { params }: ItemCtx) =>
    inWorkspace(request, params, item("/teams"), (found, { id }) => {
      if (!isAdmin(found.me)) return refuse("adminsDeleteTeams", 403);
      const { data } = found;
      if (!data.teams.some((t) => t.id === id)) return refuse("teamGone", 404);
      if (data.knowledge.some((k) => k.access.team_id === id)) return refuse("teamHasKnowledge", 409);
      data.teams = data.teams.filter((t) => t.id !== id);
      setMembers(found, id, []);
      // Narrower, never wider: meetings shared with the team stay with their participants.
      for (const m of data.meetings)
        if (m.visibility.team_id === id) m.visibility = { level: "participants", team_id: null };
      for (const p of data.projects) if (p.team_id === id) p.team_id = null;
      return ok(found);
    }),
};
