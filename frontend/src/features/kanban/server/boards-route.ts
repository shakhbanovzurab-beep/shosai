import { NextResponse } from "next/server";

import { getTranslations } from "next-intl/server";

import { myTasks } from "@/features/workspace/server";
import { forwardToBackend } from "@/server/backend-proxy";

import type { BoardDetail, BoardIcon, BoardSummary, BoardTemplate } from "../domain/board";
import type { BoardsResponse } from "../domain/contract";
import { applyLayout, createAppBoard } from "./board-ops";
import {
  boards,
  detailOf,
  editProblem,
  getBoard,
  listBoards,
  startSync,
  summaryOf,
  workspaceTasksBoard,
} from "./demo-store";
import { problemWording, refuse, type Wording } from "./problems";
import {
  boardPatchSchema,
  createBoardSchema,
  firstIssue,
  layoutSchema,
  readJson,
  workspaceTasksSchema,
} from "./schemas";

type Params = { params: Promise<{ id: string }> };

const boardsResponse = (word: Wording): BoardsResponse => ({
  boards: listBoards(word),
  workspace_tasks: { board_id: workspaceTasksBoard.id, open: myTasks().filter((t) => t.status !== "done").length },
});
const path = (id: string, rest = "") => `/v1/kanban/boards/${encodeURIComponent(id)}${rest}`;
const notFound = () => refuse("boardNotFound", 404);

/** /api/kanban/boards */
export const boardsRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/kanban/boards");
    if (upstream) return upstream;
    return NextResponse.json<BoardsResponse>(boardsResponse(await problemWording()));
  },
  /** A new app board; its template's columns are named in the request's interface language. */
  async POST(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/kanban/boards");
    if (upstream) return upstream;
    const body = createBoardSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error), 422);
    const t = await getTranslations("kanbanBoards");
    const { name, icon, template } = body.data;
    const stored = createAppBoard(name, icon as BoardIcon, template as BoardTemplate, (column) =>
      t(`columnNames.${column}`),
    );
    return NextResponse.json<BoardSummary>(summaryOf(stored), { status: 201 });
  },
};

/** /api/kanban/boards/[id] */
export const boardRoute = {
  async GET(request: Request, { params }: Params) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, path(id));
    if (upstream) return upstream;
    const stored = getBoard(id);
    return stored ? NextResponse.json<BoardDetail>(detailOf(stored, await problemWording())) : notFound();
  },
  async PATCH(request: Request, { params }: Params) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, path(id));
    if (upstream) return upstream;
    const stored = getBoard(id);
    if (!stored) return notFound();
    const body = boardPatchSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error), 422);
    stored.board = { ...stored.board, ...body.data };
    stored.revision++;
    return NextResponse.json<BoardSummary>(summaryOf(stored, await problemWording()));
  },
  /** Removes the board here; a Jira board only stops syncing, nothing is deleted in Jira. */
  async DELETE(request: Request, { params }: Params) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, path(id));
    if (upstream) return upstream;
    if (!boards.delete(id)) return notFound();
    return new Response(null, { status: 204 });
  },
};

/** /api/kanban/boards/[id]/layout */
export const boardLayoutRoute = {
  async PUT(request: Request, { params }: Params) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, path(id, "/layout"));
    if (upstream) return upstream;
    const stored = getBoard(id);
    if (!stored) return notFound();
    const problem = editProblem(stored, true);
    if (problem) return refuse(problem.problem, problem.status);
    const body = layoutSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error), 422);
    const result = applyLayout(stored, body.data);
    return result.ok ? new Response(null, { status: 204 }) : refuse(result.problem, result.status);
  },
};

/** /api/kanban/boards/[id]/sync: a Jira board pulls the latest from Jira now. */
export const boardSyncRoute = {
  async POST(request: Request, { params }: Params) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, path(id, "/sync"));
    if (upstream) return upstream;
    const stored = getBoard(id);
    if (!stored) return notFound();
    if (!stored.board.jira) return refuse("notJiraBoard", 409);
    startSync(stored);
    return NextResponse.json<BoardSummary>(summaryOf(stored, await problemWording()));
  },
};

/** /api/kanban/workspace-tasks: the app board that shows your workspace tasks, or none. */
export const workspaceTasksRoute = {
  async PUT(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/kanban/workspace-tasks");
    if (upstream) return upstream;
    const body = workspaceTasksSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error), 422);
    const target = body.data.board_id;
    if (target !== null) {
      const stored = getBoard(target);
      if (!stored) return notFound();
      if (stored.board.jira) return refuse("jiraBoardWorkspaceTasks", 409);
    }
    workspaceTasksBoard.id = target;
    return NextResponse.json<BoardsResponse>(boardsResponse(await problemWording()));
  },
};
