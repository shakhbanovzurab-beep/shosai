import { NextResponse } from "next/server";

import { forwardToBackend } from "@/server/backend-proxy";

import type {
  MyKnowledgeResponse,
  MyMeetingsResponse,
  MySharesResponse,
  MyTasksResponse,
} from "../domain/personal-contract";
import { myKnowledge, myMeetings, myShares, myTasks } from "./personal";

/** /api/me/tasks: tasks assigned to the account in every workspace, for Productivity and Kanban. */
export const myTasksRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/me/tasks");
    if (upstream) return upstream;
    return NextResponse.json<MyTasksResponse>({ tasks: myTasks() });
  },
};

/** /api/me/meetings: meetings others shared with the account, per workspace. */
export const myMeetingsRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/me/meetings");
    if (upstream) return upstream;
    return NextResponse.json<MyMeetingsResponse>(myMeetings());
  },
};

/** /api/me/shares: where the account's recordings and files are shared. */
export const mySharesRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/me/shares");
    if (upstream) return upstream;
    return NextResponse.json<MySharesResponse>(myShares());
  },
};

/** /api/me/knowledge: what Leo may use from each workspace when the account is in Personal. */
export const myKnowledgeRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/me/knowledge");
    if (upstream) return upstream;
    return NextResponse.json<MyKnowledgeResponse>(myKnowledge());
  },
};
