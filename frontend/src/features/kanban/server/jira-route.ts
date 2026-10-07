import { NextResponse } from "next/server";

import { getConnector } from "@/features/settings/server";
import { forwardToBackend } from "@/server/backend-proxy";

import type { BoardSummary } from "../domain/board";
import type { JiraBoardsResponse } from "../domain/contract";
import { connectJiraBoard, jiraBoards } from "./board-ops";
import { summaryOf } from "./demo-store";
import { refuse } from "./problems";
import { connectJiraSchema, firstIssue, readJson } from "./schemas";

/** /api/kanban/jira/boards: the Jira boards the user's Jira connection can see, and syncing one. */
export const jiraBoardsRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/kanban/jira/boards");
    if (upstream) return upstream;
    const jira = getConnector("jira");
    return NextResponse.json<JiraBoardsResponse>({
      connected: jira?.connected === true,
      account: jira?.account ?? null,
      boards: jiraBoards(),
    });
  },
  async POST(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/kanban/jira/boards");
    if (upstream) return upstream;
    const body = connectJiraSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error), 422);
    const result = connectJiraBoard(body.data.site, body.data.board_id);
    if (!result.ok) return refuse(result.problem, result.status);
    return NextResponse.json<BoardSummary>(summaryOf(result.value), { status: 201 });
  },
};
