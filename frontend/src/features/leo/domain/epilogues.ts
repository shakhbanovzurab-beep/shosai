import { applyRunEvent, type NumberedEvent } from "./run-events";
import type { LeoMessage } from "./types";

/*
 * Эпилог Leo после одобренной карточки (Leo §5.3): тот же прогон идёт дальше, и его поток читается заново с
 * первого события — так собирается весь ответ, со словами до карточки, её итогом и словами после. Пока он идёт,
 * он заменяет в разговоре ответ с тем же id из истории; потом история перечитывается и забирает его.
 */

export interface Epilogue {
  readonly runId: string;
  /** Тред и ответ прогона — из `run.started`; до него эпилог ничего не заменяет. */
  readonly threadId: string | null;
  readonly reply: LeoMessage | null;
  /** Поток дочитан или брошен: истории пора перечитаться, а эпилогу — уступить ей место. */
  readonly ended: boolean;
}

export const startedEpilogue = (runId: string): Epilogue => ({ runId, threadId: null, reply: null, ended: false });

/** Эпилог после события его потока. */
export function appliedEpilogue(epilogue: Epilogue, event: NumberedEvent): Epilogue {
  if (event.kind === "run.started") {
    const reply: LeoMessage = {
      id: event.data.reply_id,
      role: "assistant",
      content: "",
      status: "streaming",
      steps: [],
    };
    return { ...epilogue, threadId: event.data.thread_id, reply };
  }
  return epilogue.reply ? { ...epilogue, reply: applyRunEvent(epilogue.reply, event) } : epilogue;
}

/** Разговор, где ответы идущих эпилогов заменяют свои записи истории. */
export function withEpilogues(messages: LeoMessage[], epilogues: readonly Epilogue[]): LeoMessage[] {
  const replies = new Map<string, LeoMessage>();
  for (const { reply } of epilogues) if (reply) replies.set(reply.id, reply);
  if (replies.size === 0) return messages;
  return messages.map((message) => replies.get(message.id) ?? message);
}
