/* Реакции звонка: шесть эмодзи по каналу данных, без гарантии доставки и с защитой от потока (MR-D12). */

export const REACTIONS = ["👍", "❤️", "😂", "🎉", "👏", "😮"] as const;
export type Reaction = (typeof REACTIONS)[number];

/** Не больше 10 реакций за 10 секунд от одного отправителя — у отправителя и снова у каждого получателя. */
export const REACTION_LIMIT = 10;
export const REACTION_WINDOW_MS = 10_000;
/** На экране не больше 40 реакций, каждая — 4 секунды. */
export const MAX_SHOWN_REACTIONS = 40;
export const REACTION_SHOWN_MS = 4_000;

/** Имя реакции для подписей: ключ перевода, а не сама эмодзи. */
export const REACTION_NAMES = {
  "👍": "thumbsUp",
  "❤️": "heart",
  "😂": "laugh",
  "🎉": "party",
  "👏": "clap",
  "😮": "wow",
} as const satisfies Record<Reaction, string>;

export const isReaction = (value: unknown): value is Reaction => REACTIONS.some((reaction) => reaction === value);

/** Времена реакций отправителя в окне и пропускается ли новая: список не растёт сверх лимита. */
export function admitReaction(times: readonly number[], now: number): { admitted: boolean; times: number[] } {
  const recent = times.filter((time) => now - time < REACTION_WINDOW_MS);
  if (recent.length >= REACTION_LIMIT) return { admitted: false, times: recent };
  return { admitted: true, times: [...recent, now] };
}

export type ShownReaction = { id: string; emoji: Reaction; from: string; at: number };

/** Видимые реакции: свежие, не больше 40, новые в конце. */
export const shownReactions = (shown: readonly ShownReaction[], now: number) =>
  shown.filter((reaction) => now - reaction.at < REACTION_SHOWN_MS).slice(-MAX_SHOWN_REACTIONS);

/** Пакет реакции `{v: 1, emoji}`; чужая версия или не та эмодзи — null. */
export function reactionOfPacket(payload: unknown): Reaction | null {
  if (typeof payload !== "object" || payload === null) return null;
  const { v, emoji } = payload as { v?: unknown; emoji?: unknown };
  return v === 1 && isReaction(emoji) ? emoji : null;
}
