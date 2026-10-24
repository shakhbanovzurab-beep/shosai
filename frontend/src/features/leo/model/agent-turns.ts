import type { LiveTurn } from "../domain/live-turns";
import { applyRunEvent, type NumberedEvent } from "../domain/run-events";
import type { LeoMessage } from "../domain/types";

/*
 * Ходы, которые идут сейчас, по пространству разговора (Personal, workspace): вне React, чтобы закрытая панель не
 * обрывала ход. События потока копятся и применяются один раз за кадр — ответ, приходящий десятками кусков в
 * секунду, перерисовывается не чаще экрана. Начало и конец хода применяются сразу.
 */

const EMPTY: readonly LiveTurn[] = [];
const turns = new Map<string, readonly LiveTurn[]>();
const listeners = new Set<() => void>();
let queued: Array<() => void> = [];
let scheduled = false;

export const liveTurns = (scope: string): readonly LiveTurn[] => turns.get(scope) ?? EMPTY;

export function subscribeTurns(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function notify() {
  for (const listener of listeners) listener();
}

function change(scope: string, key: string, update: (turn: LiveTurn) => LiveTurn) {
  const list = turns.get(scope);
  if (list?.some((turn) => turn.key === key))
    turns.set(
      scope,
      list.map((turn) => (turn.key === key ? update(turn) : turn)),
    );
}

/** Ход после события: начало даёт ему id сервера, остальное строит ответ. */
function applied(turn: LiveTurn, event: NumberedEvent): LiveTurn {
  if (event.kind === "run.started") {
    const { run_id, thread_id, message_id, reply_id } = event.data;
    return {
      ...turn,
      runId: run_id,
      threadId: thread_id,
      seq: event.seq,
      question: { ...turn.question, id: message_id },
      reply: { ...turn.reply, id: reply_id },
    };
  }
  const reply = applyRunEvent(turn.reply, event);
  const ended = reply.status !== "streaming" && turn.reply.status === "streaming";
  return { ...turn, seq: event.seq, reply: ended ? { ...reply, durationMs: Date.now() - turn.startedAt } : reply };
}

function flush() {
  scheduled = false;
  const work = queued;
  queued = [];
  for (const step of work) step();
  notify();
}

export function addTurn(scope: string, turn: LiveTurn) {
  turns.set(scope, [...liveTurns(scope), turn]);
  notify();
}

/** Изменение хода сразу, мимо очереди кадра: тред создан, отказ до потока, поток оборвался. */
export function updateTurn(scope: string, key: string, update: (turn: LiveTurn) => LiveTurn) {
  change(scope, key, update);
  notify();
}

/** Событие потока: применится на ближайшем кадре вместе с остальными. */
export function queueEvent(scope: string, key: string, event: NumberedEvent) {
  queued.push(() => change(scope, key, (turn) => applied(turn, event)));
  if (scheduled) return;
  scheduled = true;
  if (typeof requestAnimationFrame === "function") requestAnimationFrame(flush);
  else setTimeout(flush, 0);
}

/** Применить накопленное сейчас: перед концом хода ответ должен быть целым. */
export function flushNow() {
  if (scheduled) flush();
}

export const turnOf = (scope: string, key: string): LiveTurn | undefined =>
  liveTurns(scope).find((turn) => turn.key === key);

/** Убрать ходы, которые история уже записала, или все ходы пространства. */
export function dropTurns(scope: string, recorded: (turn: LiveTurn) => boolean) {
  const list = liveTurns(scope);
  const kept = list.filter((turn) => !recorded(turn));
  if (kept.length === list.length) return;
  turns.set(scope, kept);
  notify();
}

/** Ответ с отказом до хода или обрывом потока; ход остаётся, пока человек не спросит снова. */
export const failedReply = (reply: LeoMessage, code: string, limit?: string): LeoMessage => ({
  ...reply,
  status: "error",
  steps: reply.steps?.map((step) => (step.status === "running" ? { ...step, status: "stopped" } : step)),
  failure: limit === undefined ? { code } : { code, limit },
});
