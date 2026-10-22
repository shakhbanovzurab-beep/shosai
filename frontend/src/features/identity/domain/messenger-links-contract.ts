/*
 * Аккаунты мессенджеров человека (identity, шаг 18; контракт chats §1.1–§1.2, ADR 0063): Telegram по
 * глубокой ссылке с одноразовым токеном, Slack — по совпавшей почте с подтверждением (CF-D4). Флаг подсказки
 * в пространстве — настройка аккаунта (CF-D9): закрыл раз — не видит нигде.
 */

export type LinkedMessenger = "telegram" | "slack";

export type MessengerLink = {
  id: string;
  messenger: LinkedMessenger;
  /** `handle` — «@mara»; `name` — имя, как его показывает мессенджер. */
  account: { handle: string | null; name: string };
  /** Пространство Slack; у Telegram его нет. */
  space: { id: string; name: string } | null;
  /** `proposed` — совпадение по почте в Slack ждёт подтверждения человека. */
  state: "linked" | "proposed";
  linked_at: string | null;
  proposed_at: string | null;
};

export type MessengerLinksResponse = { items: MessengerLink[]; hint_dismissed: boolean };

export type LinkRequest = {
  id: string;
  /** `https://t.me/<bot>?start=<token>`: личный чат с ботом, где человек нажимает Start. */
  url: string;
  expires_at: string;
  status: "pending" | "linked" | "expired" | "refused";
  link: MessengerLink | null;
  refusal: "messenger_account_taken" | null;
};

export const LINK_REQUEST_TTL_MS = 10 * 60_000;

/** Коды отказов маршрутов привязки (ADR 0008). */
export const MESSENGER_LINK_PROBLEMS = ["messenger_already_linked", "request_not_found", "link_not_found"] as const;
export type MessengerLinkProblem = (typeof MESSENGER_LINK_PROBLEMS)[number];
