import type { LeoMessage } from "./types";

/*
 * Ход, который идёт сейчас: вопрос и ответ, пока сервер не записал их в историю. История — источник истины:
 * как только в ней появился ответ хода, живой ход уступает ей место. «Ещё раз» и правка последнего вопроса
 * прячут прежний ответ этого вопроса: новый его заменит.
 */

export type TurnKind = "new" | "regenerate" | "edit";

export interface LiveTurn {
  /** Ключ хода — его Idempotency-Key: тот же ключ при повторе даёт тот же прогон. */
  readonly key: string;
  readonly kind: TurnKind;
  /** Тред хода; null, пока тред нового чата создаётся. */
  readonly threadId: string | null;
  readonly question: LeoMessage;
  readonly reply: LeoMessage;
  readonly runId: string | null;
  /** Номер последнего полученного события: с него поток продолжается после обрыва. */
  readonly seq: number;
  readonly startedAt: number;
}

const removedAnswers = (history: LeoMessage[], questionId: string): LeoMessage[] => {
  const at = history.findIndex((message) => message.id === questionId);
  if (at === -1) return history;
  const next = history.findIndex((message, index) => index > at && message.role === "user");
  const end = next === -1 ? history.length : next;
  return [...history.slice(0, at + 1), ...history.slice(end)];
};

/** Разговор, как его видит человек: история и поверх неё ходы, которых в ней ещё нет. */
export function mergedConversation(history: LeoMessage[], turns: readonly LiveTurn[]): LeoMessage[] {
  let messages = history;
  const known = new Set(history.map((message) => message.id));
  for (const turn of turns) {
    if (known.has(turn.reply.id)) continue;
    if (turn.kind === "new") {
      messages = [...messages, turn.question, turn.reply];
      continue;
    }
    messages = removedAnswers(messages, turn.question.id);
    const at = messages.findIndex((message) => message.id === turn.question.id);
    // Правка меняет текст вопроса; вопрос, которого в истории нет, встаёт в конец вместе с ответом.
    messages =
      at === -1
        ? [...messages, turn.question, turn.reply]
        : [...messages.slice(0, at), turn.question, turn.reply, ...messages.slice(at + 1)];
  }
  return messages;
}

/** Ход, который история уже записала: его ответ в ней есть, и хранить его больше незачем. */
export const isRecorded = (turn: LiveTurn, history: readonly LeoMessage[]) =>
  turn.reply.status !== "streaming" && history.some((message) => message.id === turn.reply.id);
