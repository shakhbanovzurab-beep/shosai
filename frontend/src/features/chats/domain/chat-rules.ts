import type { ChatConnection, RetentionDays } from "./contract";

/*
 * Правила экранов командных чатов без слов: какие слова у проблемы, укорачивает ли срок хранения, сколько
 * минут живёт код. Слова подбирает интерфейс по возвращённым ключам.
 */

/** Одна проблема звучит по-разному в группе Telegram, открытом и закрытом канале Slack. */
export type ProblemWords =
  | "botRemovedGroup"
  | "botNotInChannel"
  | "botRemovedPrivate"
  | "rightsMissing"
  | "tokenExpired";

export function problemWords(connection: Pick<ChatConnection, "problem" | "messenger" | "kind">): ProblemWords | null {
  switch (connection.problem) {
    case null:
      return null;
    case "rights_missing":
      return "rightsMissing";
    case "token_expired":
      return "tokenExpired";
    case "bot_not_in_chat":
      if (connection.messenger === "telegram") return "botRemovedGroup";
      return connection.kind === "private_channel" ? "botRemovedPrivate" : "botNotInChannel";
  }
}

/** Новый срок короче нынешнего: старые сообщения сотрутся, это нужно подтвердить. */
export const shortensRetention = (current: RetentionDays, next: RetentionDays) => next < current;

/** Сколько целых минут коду осталось к моменту `now` (не меньше нуля); `now` — с точностью до минуты. */
export const minutesLeft = (expiresAt: string, now: number) =>
  Math.max(0, Math.floor((Date.parse(expiresAt) - now) / 60_000));
