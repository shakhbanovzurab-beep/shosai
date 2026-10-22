import { apiRequest, jsonBody } from "@/lib/api/request";

import type { ClocksReply, TimerSet } from "../domain/time-contract";

/* Часы задачи на `/v1/tasks/{id}/stopwatch*` и `/timer*` (план tasks §3.9, ADR 0061); план и факт — через PATCH задачи. */

const path = (id: string, rest: string) => `/v1/tasks/${encodeURIComponent(id)}${rest}`;

export const clocksApi = {
  stopwatch: (id: string, action: "start" | "stop" | "reset") =>
    apiRequest<ClocksReply>(path(id, `/stopwatch/${action}`), { method: "POST" }),
  setTimer: (id: string, body: TimerSet) => apiRequest<ClocksReply>(path(id, "/timer"), jsonBody("PUT", body)),
  holdTimer: (id: string, action: "pause" | "resume") =>
    apiRequest<ClocksReply>(path(id, `/timer/${action}`), { method: "POST" }),
  removeTimer: (id: string) => apiRequest<ClocksReply>(path(id, "/timer"), { method: "DELETE" }),
};
