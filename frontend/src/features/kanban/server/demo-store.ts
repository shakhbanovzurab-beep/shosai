import { getConnector } from "@/features/settings/server";

import { homeColumns, homeTasks } from "../data/home-board";
import { workColumns, workTasks } from "../data/initial-board";
import { issueToTask, JIRA_CATALOG } from "../data/jira-catalog";
import { romashkaColumns, romashkaTasks } from "../data/romashka-board";
import type { BoardDetail, BoardState, BoardSummary, Column } from "../domain/board";
import type { Problem, Wording } from "./problems";
import { reconcileWorkspaceTasks } from "./workspace-tasks";

/*
 * In-memory boards for the demo, used when BACKEND_API_URL is unset; resets on restart. Jira boards
 * "sync" for a couple of seconds, read the demo catalog, and fail when Jira is disconnected in
 * Settings › Connectors, the way a real sync would.
 */

export type StoredBoard = Omit<BoardDetail, "board"> & {
  board: Omit<BoardSummary, "task_count" | "receives_workspace_tasks">;
  /** While a Jira sync runs: when it finishes. */
  syncUntil: number | null;
  /** Why a Jira sync stopped, worded into `sync_error` in the language of each answer. */
  syncProblem: Problem | null;
};

const SYNC_MS = 2500;
const now = () => new Date().toISOString();

const appBoard = (id: string, name: string, icon: BoardSummary["icon"], columns: Column[], tasks: BoardState) => ({
  board: { id, name, icon, jira: null, created_at: "2026-09-01T09:00:00.000Z" },
  columns,
  tasks,
  revision: 1,
  syncUntil: null,
  syncProblem: null,
});

const shared = globalThis as typeof globalThis & {
  kanbanDemo?: Map<string, StoredBoard>;
  /** The board that shows the user's workspace tasks; none until they choose one (it's their board). */
  kanbanWorkspaceBoard?: { id: string | null };
};
shared.kanbanWorkspaceBoard ??= { id: null };
export const workspaceTasksBoard = shared.kanbanWorkspaceBoard;
shared.kanbanDemo ??= new Map<string, StoredBoard>([
  ["work", appBoard("work", "Work", "briefcase", workColumns, workTasks)],
  ["home", appBoard("home", "Home", "home", homeColumns, homeTasks)],
  ["romashka", appBoard("romashka", "Romashka", "rocket", romashkaColumns, romashkaTasks)],
]);
export const boards = shared.kanbanDemo;

export const jiraConnected = () => getConnector("jira")?.connected === true;

/** Advances a Jira board's sync: finishes it on time, loading the issues on the first sync. */
function advanceSync(stored: StoredBoard) {
  const link = stored.board.jira;
  if (!link) return;
  if (!jiraConnected()) {
    if (link.sync_status !== "error") {
      stored.board.jira = { ...link, sync_status: "error", sync_error: null };
      stored.syncProblem = "jiraDisconnected";
      stored.revision++;
    }
    return;
  }
  // Jira is connected again after an error: pick up where it left off.
  if (link.sync_status === "error" && stored.syncUntil === null) return startSync(stored);
  if (stored.syncUntil === null || Date.now() < stored.syncUntil) return;
  const source = JIRA_CATALOG.find((b) => b.board_id === link.board_id);
  if (source && link.last_synced_at === null) {
    stored.columns = source.columns;
    stored.tasks = Object.fromEntries(source.columns.map((c) => [c.id, (source.issues[c.id] ?? []).map(issueToTask)]));
  }
  stored.syncUntil = null;
  stored.syncProblem = null;
  stored.board.jira = { ...link, sync_status: "synced", sync_error: null, last_synced_at: now() };
  stored.revision++;
}

/** A board as the API answers it; `word` words a stopped sync's reason (without it, there is none). */
export function summaryOf(stored: StoredBoard, word?: Wording): BoardSummary {
  const task_count = Object.values(stored.tasks).reduce((sum, list) => sum + list.length, 0);
  const { jira } = stored.board;
  const sync_error = stored.syncProblem && word ? word(stored.syncProblem) : null;
  return {
    ...stored.board,
    jira: jira && { ...jira, sync_error },
    task_count,
    receives_workspace_tasks: workspaceTasksBoard.id === stored.board.id,
  };
}

export function listBoards(word?: Wording): BoardSummary[] {
  for (const stored of boards.values()) {
    advanceSync(stored);
    reconcileWorkspaceTasks(stored, workspaceTasksBoard.id === stored.board.id);
  }
  return [...boards.values()].map((stored) => summaryOf(stored, word));
}

export function getBoard(id: string): StoredBoard | null {
  const stored = boards.get(id) ?? null;
  if (stored) {
    advanceSync(stored);
    reconcileWorkspaceTasks(stored, workspaceTasksBoard.id === stored.board.id);
  }
  return stored;
}

export const detailOf = (stored: StoredBoard, word?: Wording): BoardDetail => ({
  board: summaryOf(stored, word),
  columns: stored.columns,
  tasks: stored.tasks,
  revision: stored.revision,
});

/** Starts a Jira sync: the first one loads the board; later ones pick up changes made in Jira. */
export function startSync(stored: StoredBoard) {
  const link = stored.board.jira;
  if (!link) return;
  stored.syncUntil = Date.now() + SYNC_MS;
  stored.syncProblem = null;
  stored.board.jira = { ...link, sync_status: "syncing", sync_error: null };
  stored.revision++;
}

/** Records a change: bumps the revision and, on a Jira board, marks it pushed to Jira just now. */
export function touch(stored: StoredBoard) {
  stored.revision++;
  const link = stored.board.jira;
  if (link && link.sync_status === "synced") stored.board.jira = { ...link, last_synced_at: now() };
}

/** Why a change can't be made on this board right now, or null. */
export function editProblem(stored: StoredBoard, appOnly: boolean): { problem: Problem; status: number } | null {
  const link = stored.board.jira;
  if (!link) return null;
  if (appOnly) return { problem: "managedInJira", status: 409 };
  if (!jiraConnected()) return { problem: "reconnectJira", status: 409 };
  if (link.last_synced_at === null) return { problem: "firstSync", status: 409 };
  return null;
}
