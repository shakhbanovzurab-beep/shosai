import type { ChatConnection, ChatSettings } from "../../domain/contract";
import type { ChatDigest } from "../../domain/digest-contract";
import type { SlackChannel, SlackInstallation } from "../../domain/slack-contract";
import type { ConnectCode, ConnectRefusal } from "../../domain/telegram-contract";

/*
 * Как моки хранят командные чаты: так, как их будет хранить слайс chats, только в памяти вкладки. Состояние
 * бота в группе Telegram (`bot_admin`) — то, что сервер узнаёт из `my_chat_member`.
 */

export type StoredConnection = ChatConnection & { bot_admin: boolean };

export type StoredCode = ConnectCode & {
  workspace_id: string;
  created_at: number;
  /** Чем кончится код при опросе (переключатель демо). */
  outcome: "connect" | "member" | "expire" | ConnectRefusal;
  status: "pending" | "connected" | "expired" | "refused";
  result_connection_id: string | null;
};

export type StoredInstallation = SlackInstallation & { workspace_id: string; domain: string };

/** Ожидающее согласие OAuth: `state` → пространство и установка, которую переподключают. */
export type PendingConsent = { workspace_id: string; installation_id: string | null; expires_at: number };

export type ChatsDemo = {
  settings: Map<string, ChatSettings>;
  connections: Map<string, StoredConnection>;
  codes: Map<string, StoredCode>;
  installations: Map<string, StoredInstallation>;
  /** Каналы каждой установки, как их отдал бы Slack. */
  channels: Map<string, Omit<SlackChannel, "connection_id">[]>;
  consents: Map<string, PendingConsent>;
  digests: Map<string, ChatDigest>;
  /** Сколько групп Telegram уже «подключили» кодами: следующая берётся по кругу. */
  joined: number;
};
