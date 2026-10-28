/* Чат звонка: сообщения сервера по id и seq, догон после переподключения, непрочитанное (MR-D11). */

export const CHAT_TEXT_MAX = 2_000;

export type ChatMessage = { id: string; seq: number; identity: string; author: string; text: string; sentAt: string };

/** Добавить пришедшие сообщения: дубликат по id отбрасывается, порядок — по seq. */
export function mergeChat(log: readonly ChatMessage[], incoming: readonly ChatMessage[]): ChatMessage[] {
  const known = new Set(log.map((message) => message.id));
  const fresh = incoming.filter((message) => !known.has(message.id) && known.add(message.id));
  if (fresh.length === 0) return [...log];
  return [...log, ...fresh].toSorted((a, b) => a.seq - b.seq);
}

/** С какого seq догонять после переподключения: последний, что есть, или 0 — всё. */
export const lastSeq = (log: readonly ChatMessage[]) => log.at(-1)?.seq ?? 0;

/** Непрочитанные чужие сообщения после прочитанного seq. */
export const unreadCount = (log: readonly ChatMessage[], readSeq: number, self: string) =>
  log.filter((message) => message.seq > readSeq && message.identity !== self).length;

/** Текст, который можно отправить: без пустого и не длиннее 2 000 символов. */
export const sendableText = (text: string) => {
  const trimmed = text.trim();
  return trimmed.length > 0 && [...trimmed].length <= CHAT_TEXT_MAX ? trimmed : null;
};

/** Пакет чата `{v: 1, id, seq, identity, author, text, sent_at}` от сервера; иначе null. */
export function chatOfPacket(payload: unknown): ChatMessage | null {
  if (typeof payload !== "object" || payload === null) return null;
  const packet = payload as Record<string, unknown>;
  const { v, id, seq, identity, author, text, sent_at: sentAt } = packet;
  if (v !== 1 || typeof seq !== "number") return null;
  if ([id, identity, author, text, sentAt].some((field) => typeof field !== "string")) return null;
  return { id, seq, identity, author, text, sentAt } as ChatMessage;
}
