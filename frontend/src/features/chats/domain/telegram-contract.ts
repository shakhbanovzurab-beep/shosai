import type { Binding, ChatConnection, ChatMode } from "./contract";

/*
 * Подключение группы Telegram одноразовым кодом (chats §1.1–§1.2): код едет в ссылке `startgroup`, бот
 * получает его, когда его добавляют в группу; кабинет опрашивает статус кода, пока окно открыто.
 */

export type ConnectCode = {
  id: string;
  /** 8 знаков без 0, O, 1, I; на экране — «K7QM-4PZX», в ссылке и команде — без дефиса. */
  code: string;
  expires_at: string;
  bot_username: string;
  mode: ChatMode;
  binding: Binding;
  /** `https://t.me/<bot>?startgroup=<code>`: выбрать группу и добавить в неё бота. */
  add_url: string;
  /** То же с `&admin=…`: добавить бота администратором — для режима «Каждое сообщение» (CF-D1). */
  add_as_admin_url: string;
  /** `/connect@<bot> <code>` — если бота добавляют руками. */
  command: string;
  /** Код для повторного подключения существующего чата. */
  connection_id: string | null;
};

export const CONNECT_REFUSALS = ["chat_already_connected", "not_a_group", "wrong_chat", "connections_full"] as const;
export type ConnectRefusal = (typeof CONNECT_REFUSALS)[number];

export type ConnectStatus = {
  status: "pending" | "connected" | "expired" | "refused";
  connection: ChatConnection | null;
  refusal: ConnectRefusal | null;
};

export type ConnectCodeCreate = {
  project_id: string | null;
  mode: ChatMode;
  data_notice_accepted: true;
  connection_id?: string;
};

/** Алфавит кода: без знаков, которые путают на слух и на глаз. */
export const CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
export const CODE_LENGTH = 8;

/** Код для глаз: две группы по четыре знака. */
export const displayCode = (code: string) =>
  code.length === CODE_LENGTH ? `${code.slice(0, 4)}-${code.slice(4)}` : code;
