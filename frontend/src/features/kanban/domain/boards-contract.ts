import type { BoardIcon, BoardTemplate, ColumnKind, JiraLink } from "./board";
import type { BoardSticker, Color } from "./stickers-contract";
import type { Card, Priority } from "./tasks-contract";

/*
 * Доски, колонки и карточки: маршруты `/v1/boards/*` плана tasks (§3.3) и TK-D12 (§3.8). Доски — личные
 * (TK-D1); карточка — задача, её id — id задачи.
 */

export type ColumnHead = { id: string; title: string; kind: ColumnKind; color: Color | null; collapsed: boolean };
export type Column = ColumnHead & { cards: Card[] };

export type BoardSummary = {
  id: string;
  name: string;
  icon: BoardIcon;
  /** null у доски в приложении; у доски, синхронной с Jira, — откуда она и как идёт синхронизация. */
  jira: JiraLink | null;
  /** Сюда приходят задачи, назначенные человеку, и задачи его встреч (TK-D4). */
  incoming: boolean;
  task_count: number;
  created_at: string;
};

/** Доска целиком в пределах TK-D5: открытые карточки и закрытые за последние 30 дней. */
export type BoardDetail = {
  board: BoardSummary;
  stickers: BoardSticker[];
  columns: Column[];
  revision: number;
  /** Момент ответа сервера: по нему экран сверяет свои часы (ADR 0061). */
  server_now: string;
};

/** `incoming.open` — сколько открытых входящих задач ждёт доску, пока она не выбрана. */
export type BoardsResponse = { items: BoardSummary[]; incoming: { board_id: string | null; open: number } };

export type BoardCreate = { name: string; icon: BoardIcon; template: BoardTemplate };
export type BoardPatch = { name?: string; icon?: BoardIcon };
export type IncomingTarget = { board_id: string | null };

/** Вся раскладка: порядок и названия колонок, порядок карточек в каждой (409 `board_changed`, если наборы разошлись). */
export type Layout = { columns: { id: string; title: string; task_ids: string[] }[] };

export type CardCreate = { title: string; column_id: string; position: number; copy_of?: string };
/** Перемещение передаёт `column_id` и `position` вместе. */
export type CardPatch = { title?: string; priority?: Priority | null; column_id?: string; position?: number };

export type ColumnCreate = { title: string; kind: ColumnKind; position: number; color?: Color | null };
export type ColumnPatch = { title?: string; color?: Color | null; collapsed?: boolean; position?: number };

/** Доска Jira, которую видит подключение человека. */
export type JiraBoard = {
  site: string;
  board_id: number;
  name: string;
  project_key: string;
  project_name: string;
  type: "kanban" | "scrum";
  /** Доска в приложении, уже синхронная с ней. */
  synced_board_id: string | null;
};
/** Без подключения Jira (Настройки › Подключения) — `connected: false` и пустой список. */
export type JiraAvailable = { connected: boolean; account: string | null; items: JiraBoard[] };
export type JiraConnect = { site: string; board_id: number };

export const BOARDS_MAX = 50;
export const BOARD_COLUMNS_MAX = 20;
export const BOARD_OPEN_CARDS_MAX = 1000;
/** Закрытые карточки остаются на доске столько дней после закрытия (TK-D5). */
export const DONE_VISIBLE_DAYS = 30;
