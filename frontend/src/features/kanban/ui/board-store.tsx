"use client";

import { createContext, type Dispatch, type ReactNode, type SetStateAction, use, useState } from "react";

import { useTranslations } from "use-intl";

import { NameDialog, type NameRequest } from "@/components/name-dialog";

import type { BoardDetail, BoardState, BoardSummary, ColumnKind } from "../domain/board";
import { type BoardCommands, createBoardCommands } from "./board-commands";

type BoardContextValue = {
  summary: BoardSummary;
  /** False while a Jira board is disconnected or still on its first sync: the board is read-only. */
  editable: boolean;
  /** Jira owns the columns, and deleting or duplicating issues is done in Jira. */
  managedByJira: boolean;
  board: BoardState;
  setBoard: Dispatch<SetStateAction<BoardState>>;
  columnOrder: string[];
  setColumnOrder: Dispatch<SetStateAction<string[]>>;
  columnTitle: (columnId: string) => string;
  columnKind: (columnId: string) => ColumnKind;
  actions: BoardCommands;
};

const BoardContext = createContext<BoardContextValue | null>(null);

export function useBoard() {
  const value = use(BoardContext);
  if (!value) throw new Error("useBoard must be used inside <BoardProvider>");
  return value;
}

/** One board's tasks and columns as the user edits them; remount it (by `key`) when the server's copy changes. */
export function BoardProvider({ initialDetail, children }: { initialDetail: BoardDetail; children: ReactNode }) {
  const detail = initialDetail;
  const [board, setBoard] = useState<BoardState>(detail.tasks);
  const [columnOrder, setColumnOrder] = useState(() => detail.columns.map((c) => c.id));
  const [titles, setTitles] = useState(() => Object.fromEntries(detail.columns.map((c) => [c.id, c.title])));
  const [nameRequest, setNameRequest] = useState<NameRequest | null>(null);
  const t = useTranslations("kanban");
  const tc = useTranslations("common");

  const summary = detail.board;
  const jira = summary.jira;
  const kinds = new Map(detail.columns.map((c) => [c.id, c.kind]));
  const actions = createBoardCommands({
    boardId: summary.id,
    board,
    setBoard,
    columnOrder,
    setColumnOrder,
    titles,
    setTitles,
    requestName: setNameRequest,
    t,
    tc,
  });

  const value: BoardContextValue = {
    summary,
    editable: !jira || (jira.sync_status !== "error" && jira.last_synced_at !== null),
    managedByJira: jira !== null,
    board,
    setBoard,
    columnOrder,
    setColumnOrder,
    columnTitle: (id) => titles[id] ?? "",
    columnKind: (id) => kinds.get(id) ?? "todo",
    actions,
  };

  return (
    <BoardContext value={value}>
      {children}
      <NameDialog request={nameRequest} onClose={() => setNameRequest(null)} />
    </BoardContext>
  );
}
