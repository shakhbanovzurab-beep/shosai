import { getConnector } from "@/features/settings/mocks/demo-connectors";
import { getTranslations } from "@/mocks/runtime";

import type { BoardIcon, BoardTemplate } from "../../domain/board";
import type { BoardDetail, BoardSummary, BoardsResponse, JiraAvailable } from "../../domain/boards-contract";
import { applyLayout, createBoard, deleteBoard, setIncoming } from "../store/board-ops";
import { availableJiraBoards, connectJiraBoard, startSync } from "../store/jira";
import { openIncoming, reconcile } from "../store/landing";
import { boardDetailOf, summaryOf } from "../store/present";
import { demo, touch } from "../store/state";
import { boardCreateSchema, boardPatchSchema, incomingSchema, jiraConnectSchema, layoutSchema } from "./board-schemas";
import { bodyOf, json, noContent, type Params, refuse } from "./http";
import { answer, answerEmpty, withBoard } from "./respond";

/* `/v1/boards*`: список, создание, доска, раскладка, доска входящих, Jira (план tasks §3.3). */

function boardsResponse(): BoardsResponse {
  reconcile();
  const d = demo();
  return {
    items: [...d.boards.values()].map(summaryOf),
    incoming: { board_id: d.incoming.board_id, open: openIncoming() },
  };
}

/** /v1/boards */
export const boardsRoute = {
  async GET() {
    return json(boardsResponse());
  },
  /** Колонки шаблона названы на языке запроса, как их называет сервер. */
  async POST(request: Request) {
    const body = await bodyOf(request, boardCreateSchema);
    if ("refusal" in body) return body.refusal;
    const t = await getTranslations("kanbanBoards");
    const { name, icon, template } = body.data;
    const created = createBoard(name, icon as BoardIcon, template as BoardTemplate, (c) => t(`columnNames.${c}`));
    return answer(created, summaryOf, 201);
  },
};

/** /v1/boards/incoming */
export const incomingRoute = {
  async PUT(request: Request) {
    const body = await bodyOf(request, incomingSchema);
    if ("refusal" in body) return body.refusal;
    const set = setIncoming(body.data.board_id);
    return set.ok ? json(boardsResponse()) : refuse(set.code);
  },
};

/** /v1/boards/[id] */
export const boardRoute = {
  async GET(_request: Request, { params }: Params<"id">) {
    return withBoard(params, (board) => json<BoardDetail>(boardDetailOf(board)));
  },
  async PATCH(request: Request, { params }: Params<"id">) {
    return withBoard(params, async (board) => {
      const body = await bodyOf(request, boardPatchSchema);
      if ("refusal" in body) return body.refusal;
      if (body.data.name !== undefined) board.name = body.data.name;
      if (body.data.icon !== undefined) board.icon = body.data.icon;
      touch(board);
      return json<BoardSummary>(summaryOf(board));
    });
  },
  async DELETE(_request: Request, { params }: Params<"id">) {
    return withBoard(params, (board) => {
      deleteBoard(board);
      return noContent();
    });
  },
};

/** /v1/boards/[id]/layout */
export const layoutRoute = {
  async PUT(request: Request, { params }: Params<"id">) {
    return withBoard(params, async (board) => {
      const body = await bodyOf(request, layoutSchema);
      if ("refusal" in body) return body.refusal;
      return answerEmpty(applyLayout(board, body.data));
    });
  },
};

/** /v1/boards/[id]/sync: доска Jira забирает последнее из Jira сейчас. */
export const syncRoute = {
  async POST(_request: Request, { params }: Params<"id">) {
    return withBoard(params, (board) => {
      if (!board.jira) return refuse("not_jira_board");
      startSync(board);
      return json<BoardSummary>(summaryOf(board));
    });
  },
};

/** /v1/boards/jira/available */
export const jiraAvailableRoute = {
  async GET() {
    const jira = getConnector("jira");
    return json<JiraAvailable>({
      connected: jira?.connected === true,
      account: jira?.account ?? null,
      items: availableJiraBoards(),
    });
  },
};

/** /v1/boards/jira */
export const jiraConnectRoute = {
  async POST(request: Request) {
    const body = await bodyOf(request, jiraConnectSchema);
    if ("refusal" in body) return body.refusal;
    const board = connectJiraBoard(body.data.site, body.data.board_id);
    return typeof board === "string" ? refuse(board) : json<BoardSummary>(summaryOf(board), 201);
  },
};
