/*
 * Командные чаты пространства: контракт `/v1/workspaces/{id}/chats*` плана chats (§1, ADR 0062, ADR 0063).
 * snake_case, ошибки — коды ADR 0008 (`problems.ts`), страницы — `{items, next_cursor}`. Пока бэкенда нет,
 * его отдают моки слайса; слайс chats потом меняет только источник данных.
 */

export const MESSENGERS = ["telegram", "slack"] as const;
export type Messenger = (typeof MESSENGERS)[number];

/** «Только сообщения для Leo» или «Каждое сообщение, для дайджестов». */
export const CHAT_MODES = ["mentions", "all"] as const;
export type ChatMode = (typeof CHAT_MODES)[number];

/** Куда идут задачи из чата: пространство целиком или один его проект. */
export type Binding = { kind: "workspace" } | { kind: "project"; project: { id: string; name: string } };

/** Что сломалось: бота нет в чате, у бота нет прав администратора (CF-D1), доступ Slack кончился. */
export const CHAT_PROBLEMS = ["bot_not_in_chat", "rights_missing", "token_expired"] as const;
export type ChatProblem = (typeof CHAT_PROBLEMS)[number];

export type ChatKind = "group" | "supergroup" | "public_channel" | "private_channel";
export type PersonRef = { user_id: string; name: string };

export type ChatConnection = {
  id: string;
  workspace_id: string;
  messenger: Messenger;
  /** Название чата, как его называет мессенджер. */
  title: string;
  kind: ChatKind;
  binding: Binding;
  mode: ChatMode;
  state: "working" | "needs_attention";
  /** Есть ровно тогда, когда `state` = needs_attention. */
  problem: ChatProblem | null;
  /** Последнее сообщение, которое Shosai получил из чата. */
  last_activity_at: string | null;
  /** С какого момента у Shosai есть сообщения чата: вход бота или подключение Slack (CF-D3). */
  history_from: string;
  /** Что сотрёт отключение. */
  stored: { messages: number; oldest_at: string | null };
  connected_at: string;
  connected_by: PersonRef;
  slack: { installation_id: string; channel_id: string } | null;
};

export type ChatConnectionsPage = { items: ChatConnection[]; next_cursor: string | null };

export const RETENTION_DAYS = [30, 90, 365] as const;
export type RetentionDays = (typeof RETENTION_DAYS)[number];

export type ServedMessenger =
  | { messenger: "telegram"; bot_username: string }
  | { messenger: "slack"; app_name: string };

export type ChatSettings = {
  retention_days: RetentionDays;
  /** Дом данных пространства: там хранятся сообщения его чатов. */
  home: "ru" | "eu";
  /** Только мессенджеры, которые обслуживает эта установка; остальные не предлагаются. */
  messengers: ServedMessenger[];
  limits: { connections: number };
};

export type ChatSettingsPatch = { retention_days: RetentionDays };

/** Изменение подключения по присутствию поля; к режиму `all` нужно согласие с уведомлением о данных. */
export type ChatConnectionPatch = { project_id?: string | null; mode?: ChatMode; data_notice_accepted?: boolean };

export const CONNECTIONS_MAX = 50;
export const CONNECT_CODE_TTL_MS = 30 * 60_000;
export const POLL_INTERVAL_MS = 2_000;
