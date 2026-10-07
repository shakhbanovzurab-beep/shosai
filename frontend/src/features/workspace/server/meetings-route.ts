import { NextResponse } from "next/server";

import type { DecisionsResponse, MeetingsResponse, TeamMeetingDetail } from "../domain/content-contract";
import { isAdmin } from "../domain/roles";
import { type Ctx, type Found, type ItemCtx, inWorkspace, item } from "./guards";
import { type Problem, refuse } from "./problems";
import { listDecisions, listMeetings, meetingDetail } from "./projection";
import { firstIssue, meetingShareSchema, readJson, shareRecordingSchema } from "./schemas";
import { shareRecording, withdrawRecording } from "./sharing";
import { listUpcoming } from "./upcoming";

/** Team and project must belong to this workspace. */
function checkRefs(
  { data }: Found,
  input: { visibility?: { team_id: string | null }; project_id?: string | null },
): Problem | null {
  if (input.visibility?.team_id && !data.teams.some((t) => t.id === input.visibility?.team_id)) return "teamGone";
  if (input.project_id && !data.projects.some((p) => p.id === input.project_id)) return "projectGone";
  return null;
}

/** /api/workspaces/[ws]/meetings: what's shared with the member, and sharing one of their recordings here. */
export const meetingsRoute = {
  GET: (request: Request, { params }: Ctx) =>
    inWorkspace(
      request,
      params,
      () => "/meetings",
      ({ data, me }) =>
        NextResponse.json<MeetingsResponse>({ meetings: listMeetings(data, me), upcoming: listUpcoming(data, me) }),
    ),

  POST: (request: Request, { params }: Ctx) =>
    inWorkspace(
      request,
      params,
      () => "/meetings",
      async (found) => {
        const body = shareRecordingSchema.safeParse(await readJson(request));
        if (!body.success) return refuse(firstIssue(body.error), 422);
        const problem = checkRefs(found, body.data);
        if (problem) return refuse(problem, 422);
        const meeting = shareRecording(found.data, found.me, body.data);
        if (!meeting) return refuse("recordingNotFound", 404);
        const shared = meetingDetail(found.data, found.me, meeting.id);
        return shared ? NextResponse.json<TeamMeetingDetail>(shared, { status: 201 }) : refuse("meetingNotFound", 404);
      },
    ),
};

/** /api/workspaces/[ws]/meetings/[id] */
export const meetingRoute = {
  GET: (request: Request, { params }: ItemCtx) =>
    inWorkspace(request, params, item("/meetings"), ({ data, me }, { id }) => {
      const meeting = meetingDetail(data, me, id);
      return meeting ? NextResponse.json<TeamMeetingDetail>(meeting) : refuse("meetingNotFound", 404);
    }),

  /** Who sees it, the transcript, the project: its organizer or an admin. */
  PATCH: (request: Request, { params }: ItemCtx) =>
    inWorkspace(request, params, item("/meetings"), async (found, { id }) => {
      const { data, me } = found;
      const stored = data.meetings.find((m) => m.id === id);
      if (!stored || !meetingDetail(data, me, id)) return refuse("meetingNotFound", 404);
      if (stored.organizer_id !== me.id && !isAdmin(me)) return refuse("meetingShareDenied", 403);
      const body = meetingShareSchema.safeParse(await readJson(request));
      if (!body.success) return refuse(firstIssue(body.error), 422);
      const problem = checkRefs(found, body.data);
      if (problem) return refuse(problem, 422);
      const { visibility, transcript_shared, project_id } = body.data;
      if (visibility) stored.visibility = visibility;
      if (transcript_shared !== undefined) stored.transcript_shared = transcript_shared;
      if (project_id !== undefined) stored.project_id = project_id;
      const updated = meetingDetail(data, me, id);
      return updated ? NextResponse.json<TeamMeetingDetail>(updated) : refuse("meetingNotFound", 404);
    }),

  /** Stops sharing: the recording goes back to its owner's Notes only. The organizer, or an admin. */
  DELETE: (request: Request, { params }: ItemCtx) =>
    inWorkspace(request, params, item("/meetings"), ({ data, me }, { id }) => {
      const stored = data.meetings.find((m) => m.id === id);
      if (!stored || !meetingDetail(data, me, id)) return refuse("meetingNotFound", 404);
      if (stored.organizer_id !== me.id && !isAdmin(me)) return refuse("meetingUnshareDenied", 403);
      withdrawRecording(id);
      return new Response(null, { status: 204 });
    }),
};

/** /api/workspaces/[ws]/decisions */
export const decisionsRoute = {
  GET: (request: Request, { params }: Ctx) =>
    inWorkspace(
      request,
      params,
      () => "/decisions",
      ({ data, me }) => NextResponse.json<DecisionsResponse>({ decisions: listDecisions(data, me) }),
    ),
};
