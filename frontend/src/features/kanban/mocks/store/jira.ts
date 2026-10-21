import { getConnector } from "@/features/settings/mocks/demo-connectors";

import { JIRA_CATALOG, JIRA_SITE } from "../../data/jira-catalog";
import type { JiraBoard } from "../../domain/boards-contract";
import type { KanbanProblem } from "../../domain/problems";
import type { Priority } from "../../domain/tasks-contract";
import { seedTask } from "../seed/builders";
import { demo, now } from "./state";
import type { StoredBoard, StoredColumn } from "./types";

/*
 * Доски Jira в демо: «синхронизация» идёт пару секунд, читает демо-каталог и останавливается с ошибкой, когда
 * Jira отключена в Настройках › Подключения, как настоящая синхронизация (план tasks, шаги 12–15).
 */

const SYNC_MS = 2500;
const PRIORITY: Record<string, Priority> = { High: "high", Medium: "medium", Low: "low" };

export const jiraConnected = () => getConnector("jira")?.connected === true;

export function startSync(board: StoredBoard) {
  if (!board.jira) return;
  board.syncUntil = Date.now() + SYNC_MS;
  board.jira = { ...board.jira, sync_status: "syncing", sync_error: null };
  board.revision++;
}

/** Первая синхронизация приносит колонки и задачи доски Jira. */
function importIssues(board: StoredBoard, boardId: number) {
  const source = JIRA_CATALOG.find((b) => b.board_id === boardId);
  if (!source) return;
  const d = demo();
  board.columns = source.columns.map((column): StoredColumn => {
    const ids = (source.issues[column.id] ?? []).map(([key, summary, type, priority, assignee]) => {
      const task = seedTask(`jira-${key}`, summary, "", {
        status: column.kind,
        priority: PRIORITY[priority] ?? null,
        assignee: assignee ? { user_id: null, name: assignee } : null,
        source: { kind: "jira", meeting: null, finding: null },
        jira: { key, url: `https://${JIRA_SITE}/browse/${key}`, type },
      });
      d.tasks.set(task.id, task);
      return task.id;
    });
    return { id: column.id, title: column.title, kind: column.kind, color: null, collapsed: false, card_ids: ids };
  });
}

/** Двигает синхронизацию доски Jira: заканчивает её вовремя или останавливает, если Jira отключена. */
export function advanceSync(board: StoredBoard) {
  const link = board.jira;
  if (!link) return;
  if (!jiraConnected()) {
    if (link.sync_status !== "error") {
      board.jira = { ...link, sync_status: "error", sync_error: "reconnect_jira" };
      board.revision++;
    }
    return;
  }
  if (link.sync_status === "error" && board.syncUntil === null) return startSync(board);
  if (board.syncUntil === null || Date.now() < board.syncUntil) return;
  if (link.last_synced_at === null) importIssues(board, link.board_id);
  board.syncUntil = null;
  board.jira = { ...link, sync_status: "synced", sync_error: null, last_synced_at: now() };
  board.revision++;
}

const syncedWith = (boardId: number) =>
  [...demo().boards.values()].find((b) => b.jira?.board_id === boardId)?.id ?? null;

export function availableJiraBoards(): JiraBoard[] {
  if (!jiraConnected()) return [];
  return JIRA_CATALOG.map(({ board_id, name, project_key, project_name, type }) => ({
    site: JIRA_SITE,
    board_id,
    name,
    project_key,
    project_name,
    type,
    synced_board_id: syncedWith(board_id),
  }));
}

/** Новая доска, синхронная с доской Jira; код отказа, если это нельзя. */
export function connectJiraBoard(site: string, boardId: number): StoredBoard | KanbanProblem {
  if (!jiraConnected()) return "connect_jira_first";
  const source = JIRA_CATALOG.find((b) => b.board_id === boardId);
  if (site !== JIRA_SITE || !source) return "jira_board_unavailable";
  if (syncedWith(boardId)) return "jira_board_synced";
  const board: StoredBoard = {
    id: crypto.randomUUID(),
    name: source.name,
    icon: "rocket",
    created_at: now(),
    jira: {
      site,
      project_key: source.project_key,
      board_id: boardId,
      board_name: source.name,
      board_url: `https://${site}/jira/software/projects/${source.project_key}/boards/${boardId}`,
      sync_status: "syncing",
      sync_error: null,
      last_synced_at: null,
    },
    syncUntil: null,
    revision: 1,
    columns: [],
    system: { assignee: true, due: true, priority: true, recurrence: false },
    stickers: [],
  };
  demo().boards.set(board.id, board);
  startSync(board);
  return board;
}

/** Код, почему доску Jira сейчас нельзя менять, или null. `appOnly` — изменение, которое делают только в Jira. */
export function jiraRefusal(board: StoredBoard, appOnly: boolean): KanbanProblem | null {
  const link = board.jira;
  if (!link) return null;
  if (appOnly) return "managed_in_jira";
  if (!jiraConnected()) return "reconnect_jira";
  if (link.last_synced_at === null) return "first_sync";
  return null;
}
