import { ApiError } from "@/lib/api/errors";

import { agentApi } from "../api/agent-api";
import { isTerminal } from "../domain/run-events";
import { onCardEvent } from "./card-events";
import { endEpilogue, queueEpilogueEvent, startEpilogue } from "./epilogues";
import { readRun } from "./run-stream";

/*
 * Поток прогона после одобрения: итог карточки (`action.updated`) и эпилог Leo или конец прогона. Поток читается с
 * первого события — так эпилог собирает весь ответ. Пока итога нет, сервер закрывает поток на паузе этой карточки:
 * он читается снова с растущей паузой, всего около трёх минут. Пауза на новой карточке эпилога — конец: её решат
 * потом. Брошенный поток не беда: история и «Нужны вы» перечитаются и покажут итог.
 */

const PAUSES_MS = [1_000, 2_000, 3_000, 5_000, 8_000, 13_000, 20_000, 30_000, 30_000, 30_000, 30_000];

const following = new Set<string>();
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

type Reading = { seq: number; pausedOn: string | null };
type Outcome = "ended" | "waiting" | "gone";

async function readOnce(runId: string, actionId: string, reading: Reading): Promise<Outcome> {
  try {
    const stream = await agentApi.resume(runId, reading.seq, new AbortController().signal);
    const ended = await readRun(stream, (event) => {
      reading.seq = event.seq;
      if (event.kind === "run.paused") reading.pausedOn = event.data.action_id;
      queueEpilogueEvent(runId, event);
      onCardEvent(event);
      return isTerminal(event);
    });
    if (ended || (reading.pausedOn !== null && reading.pausedOn !== actionId)) return "ended";
    return "waiting";
  } catch (error) {
    // Журнал прогона истёк или прогона нет: ждать нечего, история покажет, чем всё кончилось.
    if (error instanceof ApiError && error.status < 500 && error.status !== 429) return "gone";
    return "waiting";
  }
}

/** Вести поток прогона одобренной карточки до конца эпилога; повторный вызов для того же прогона не нужен. */
export async function followRun(runId: string, actionId: string): Promise<void> {
  if (following.has(runId)) return;
  following.add(runId);
  startEpilogue(runId);
  const reading: Reading = { seq: 0, pausedOn: null };
  try {
    for (const pause of [0, ...PAUSES_MS]) {
      if (pause > 0) await sleep(pause);
      if ((await readOnce(runId, actionId, reading)) !== "waiting") return;
    }
  } finally {
    following.delete(runId);
    endEpilogue(runId);
  }
}
