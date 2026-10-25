import { ApiError } from "@/lib/api/errors";

import { agentApi, type TurnBody } from "../api/agent-api";
import { isPause, isTerminal, type NumberedEvent } from "../domain/run-events";
import type { LeoMessage } from "../domain/types";
import { dropTurns, failedReply, flushNow, queueEvent, turnOf, updateTurn } from "./agent-turns";
import { onCardEvent } from "./card-events";
import { readRun } from "./run-stream";

/*
 * Один ход до его конца: поток открывается запросом хода, а оборвавшийся продолжается с последнего события
 * (`Last-Event-ID`), несколько раз с растущей паузой. Прогон идёт на сервере сам: обрыв сети не обрывает ответ.
 * Журнал, истёкший за час, — повод перечитать историю, а не ошибка. «Стоп» просит сервер остановить прогон.
 * Карточка ставит прогон на паузу: ход здесь кончается, а после решения поток ведёт эпилог (run-follower).
 */

const RESUME_PAUSES_MS = [500, 1_000, 2_000, 4_000, 8_000];
// Код обрыва, который не дал продолжить поток: панель пишет его словами «проверьте соединение».
const CONNECTION = "connection";

export interface TurnRun {
  readonly scope: string;
  readonly key: string;
  readonly threadId: string;
  readonly body: TurnBody;
  /** Кабинет открывает страницу, о которой попросил человек (`client.action`). */
  readonly onNavigate: (path: string) => void;
  /** Ход закончился так или иначе: история треда перечитывается и забирает его. */
  readonly onSettled: () => void;
}

const stopAsked = new Set<string>();
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const endsTurn = (event: NumberedEvent) => isTerminal(event) || isPause(event);

const read = (stream: ReadableStream<Uint8Array>, run: TurnRun) =>
  readRun(stream, (event) => {
    handle(run, event);
    return endsTurn(event);
  });

function handle(run: TurnRun, event: NumberedEvent) {
  if (event.kind === "run.started" && stopAsked.delete(run.key)) {
    // Ответ на «Стоп» придёт событием конца; не дошедшая просьба оставит ход идти, как без неё.
    agentApi
      .cancel(event.data.run_id)
      .catch((error: unknown) => console.warn("Leo: просьба остановить ход не дошла", error));
  }
  if (event.kind === "client.action" && event.data.navigate) run.onNavigate(event.data.navigate.to);
  queueEvent(run.scope, run.key, event);
  onCardEvent(event);
  if (event.kind === "run.started" || endsTurn(event)) flushNow();
}

const fail = (run: TurnRun, code: string, limit?: string) =>
  updateTurn(run.scope, run.key, (turn) => ({ ...turn, reply: failedReply(turn.reply, code, limit) }));

/** Код отказа и лимит из ошибки запроса; сеть и неизвестный сбой — обрыв соединения. */
export function refusal(error: unknown): [string, string | undefined] {
  if (!(error instanceof ApiError) || error.code === null) return [CONNECTION, undefined];
  const limit = error.params.limit;
  return [error.code, typeof limit === "string" ? limit : undefined];
}

async function resumed(run: TurnRun): Promise<boolean | "gone"> {
  for (const pause of RESUME_PAUSES_MS) {
    await sleep(pause);
    const turn = turnOf(run.scope, run.key);
    if (turn?.runId == null) return false;
    try {
      const stream = await agentApi.resume(turn.runId, turn.seq, new AbortController().signal);
      if (await read(stream, run)) return true;
    } catch (error) {
      if (error instanceof ApiError && error.status === 410) return "gone";
      if (error instanceof ApiError && error.status < 500 && error.status !== 429) return false;
    }
  }
  return false;
}

/** Провести ход до конца; ответ, каким он закончился, — для голосового режима. */
export async function runTurn(run: TurnRun): Promise<LeoMessage | undefined> {
  try {
    const stream = await agentApi.turn(run.threadId, run.body, run.key, new AbortController().signal);
    // Обрыв посреди чтения — не сбой хода: поток продолжится с последнего события.
    const ended = (await read(stream, run).catch(() => false)) || (await resumed(run));
    // Журнал истёк: ответ уже в истории, ход уступает ей место, а не показывает сбой.
    if (ended === "gone") dropTurns(run.scope, (turn) => turn.key === run.key);
    else if (!ended) fail(run, CONNECTION);
  } catch (error) {
    fail(run, ...refusal(error));
  } finally {
    run.onSettled();
  }
  return turnOf(run.scope, run.key)?.reply;
}

/** Остановить ход; до начала прогона — как только сервер назовёт его. Сбой просьбы — у вызывающего. */
export async function stopTurn(scope: string, key: string): Promise<void> {
  const runId = turnOf(scope, key)?.runId;
  if (runId) await agentApi.cancel(runId);
  else stopAsked.add(key);
}
