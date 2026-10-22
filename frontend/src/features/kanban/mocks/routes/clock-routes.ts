import {
  clearTimer,
  clocksOf,
  holdTimer,
  resetStopwatch,
  setTimer,
  startStopwatch,
  stopStopwatch,
} from "../store/clock-ops";
import type { Outcome } from "../store/outcome";
import { now } from "../store/state";
import type { StoredTask } from "../store/types";
import { bodyOf, type Params } from "./http";
import { answer, withTask } from "./respond";
import { timerSchema } from "./task-schemas";

/* `/v1/tasks/{id}/stopwatch/*` и `/v1/tasks/{id}/timer*` (ADR 0061): каждое действие отвечает часами задачи. */

const reply = (outcome: Outcome<null>, task: StoredTask) =>
  answer(outcome, () => ({ ...clocksOf(task), server_now: now() }));

const action = (run: (task: StoredTask) => Outcome<null>) => ({
  async POST(_request: Request, { params }: Params<"id">) {
    return withTask(params, (task) => reply(run(task), task));
  },
});

export const stopwatchStartRoute = action(startStopwatch);
export const stopwatchStopRoute = action(stopStopwatch);
export const stopwatchResetRoute = action(resetStopwatch);
export const timerPauseRoute = action((task) => holdTimer(task, true));
export const timerResumeRoute = action((task) => holdTimer(task, false));

/** /v1/tasks/[id]/timer: задать заново и убрать. */
export const timerRoute = {
  async PUT(request: Request, { params }: Params<"id">) {
    return withTask(params, async (task) => {
      const body = await bodyOf(request, timerSchema);
      if ("refusal" in body) return body.refusal;
      return reply(setTimer(task, body.data.length_ms), task);
    });
  },
  async DELETE(_request: Request, { params }: Params<"id">) {
    return withTask(params, (task) => reply(clearTimer(task), task));
  },
};
