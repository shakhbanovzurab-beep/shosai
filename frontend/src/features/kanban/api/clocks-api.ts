import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

import type { ClocksReply, TimerSet } from "../domain/time-contract";

/* Часы задачи на `/v1/tasks/{id}/stopwatch*` и `/timer*` (план tasks §3.9, ADR 0061); план и факт — через PATCH задачи. */

const task = (id: string) => ({ params: { path: { task_id: id } } });
const STOPWATCH = {
  start: "/v1/tasks/{task_id}/stopwatch/start",
  stop: "/v1/tasks/{task_id}/stopwatch/stop",
  reset: "/v1/tasks/{task_id}/stopwatch/reset",
} as const;
const HOLD = { pause: "/v1/tasks/{task_id}/timer/pause", resume: "/v1/tasks/{task_id}/timer/resume" } as const;

export const clocksApi = {
  stopwatch: (id: string, action: keyof typeof STOPWATCH): Promise<ClocksReply> =>
    dataOf(apiClient.POST(STOPWATCH[action], task(id))),
  setTimer: (id: string, body: TimerSet): Promise<ClocksReply> =>
    dataOf(apiClient.PUT("/v1/tasks/{task_id}/timer", { ...task(id), body })),
  holdTimer: (id: string, action: keyof typeof HOLD): Promise<ClocksReply> =>
    dataOf(apiClient.POST(HOLD[action], task(id))),
  removeTimer: (id: string): Promise<ClocksReply> => dataOf(apiClient.DELETE("/v1/tasks/{task_id}/timer", task(id))),
};
