import { appliedEpilogue, type Epilogue, startedEpilogue } from "../domain/epilogues";
import type { NumberedEvent } from "../domain/run-events";
import { flushFrame, onNextFrame } from "./frame-queue";

/*
 * Идущие эпилоги по прогону — вне React: одобрение с главной («Нужны вы») ведёт эпилог и без открытой панели,
 * а открытая панель показывает его в своём треде. События применяются раз за кадр.
 */

const EMPTY: readonly Epilogue[] = [];
let epilogues: readonly Epilogue[] = EMPTY;
const listeners = new Set<() => void>();

export const liveEpilogues = () => epilogues;

export function subscribeEpilogues(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function notify() {
  for (const listener of listeners) listener();
}

function change(runId: string, update: (epilogue: Epilogue) => Epilogue) {
  epilogues = epilogues.map((epilogue) => (epilogue.runId === runId ? update(epilogue) : epilogue));
}

export function startEpilogue(runId: string) {
  epilogues = [...epilogues.filter((epilogue) => epilogue.runId !== runId), startedEpilogue(runId)];
  notify();
}

export function queueEpilogueEvent(runId: string, event: NumberedEvent) {
  onNextFrame(() => change(runId, (epilogue) => appliedEpilogue(epilogue, event)), notify);
}

/** Поток эпилога дочитан или брошен: накопленное применяется сразу. */
export function endEpilogue(runId: string) {
  flushFrame();
  change(runId, (epilogue) => ({ ...epilogue, ended: true }));
  notify();
}

/** Убрать эпилоги, которые перечитанная история уже забрала. */
export function dropEpilogues(runIds: ReadonlySet<string>) {
  const kept = epilogues.filter((epilogue) => !runIds.has(epilogue.runId));
  if (kept.length === epilogues.length) return;
  epilogues = kept.length === 0 ? EMPTY : kept;
  notify();
}
