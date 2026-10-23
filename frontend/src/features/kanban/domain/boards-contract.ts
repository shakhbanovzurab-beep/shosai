import type { components } from "@/lib/api/generated/schema";

/*
 * Доски, колонки и карточки: маршруты `/v1/boards/*` плана tasks (§3.3) и TK-D12 (§3.8). Доски — личные
 * (TK-D1); карточка — задача, её id — id задачи.
 */

type Schemas = components["schemas"];

export type ColumnHead = Schemas["ColumnHeadOut"];
export type Column = Schemas["ColumnOut"];

/** У доски, синхронной с Jira, — откуда она и как идёт синхронизация; `incoming` — сюда приходят задачи (TK-D4). */
export type BoardSummary = Schemas["BoardSummaryOut"];

/** Доска целиком в пределах TK-D5: открытые карточки и закрытые за последние 30 дней, и момент ответа сервера. */
export type BoardDetail = Schemas["BoardDetailOut"];

/** `incoming.open` — сколько открытых входящих задач ждёт доску, пока она не выбрана. */
export type BoardsResponse = Schemas["BoardsOut"];

export type BoardCreate = Schemas["BoardCreateBody"];
export type BoardPatch = Schemas["BoardPatchBody"];
export type IncomingTarget = Schemas["IncomingBody"];

/** Вся раскладка: порядок и названия колонок, порядок карточек в каждой (409 `board_changed`, если наборы разошлись). */
export type Layout = Schemas["LayoutBody"];

export type CardCreate = Schemas["CardCreateBody"];
/** Перемещение передаёт `column_id` и `position` вместе. */
export type CardPatch = Schemas["CardPatchBody"];

export type ColumnCreate = Schemas["ColumnCreateBody"];
export type ColumnPatch = Schemas["ColumnPatchBody"];

/** Доска Jira, которую видит подключение человека. */
export type JiraBoard = Schemas["JiraBoardOut"];
/** Без подключения Jira (Настройки › Подключения) — `connected: false` и пустой список. */
export type JiraAvailable = Schemas["JiraAvailableOut"];
export type JiraConnect = Schemas["JiraConnectBody"];

export const BOARDS_MAX = 50;
export const BOARD_COLUMNS_MAX = 20;
export const BOARD_OPEN_CARDS_MAX = 1000;
/** Закрытые карточки остаются на доске столько дней после закрытия (TK-D5). */
export const DONE_VISIBLE_DAYS = 30;
