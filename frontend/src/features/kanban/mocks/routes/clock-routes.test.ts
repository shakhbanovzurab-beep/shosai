import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { BoardDetail } from "../../domain/boards-contract";
import type { ClocksReply, StopwatchAutomations } from "../../domain/time-contract";
import { demo, resetDemo } from "../store/state";
import { boardRoute } from "./boards-routes";
import {
  stopwatchResetRoute,
  stopwatchStartRoute,
  stopwatchStopRoute,
  timerPauseRoute,
  timerResumeRoute,
  timerRoute,
} from "./clock-routes";
import { cardRoute, cardsRoute } from "./columns-cards-routes";
import { boardStickerRoute } from "./subtasks-stickers-routes";
import { taskRoute } from "./tasks-routes";
import { call, codeOf } from "./test-client";

const MINUTE = 60_000;
const T0 = Date.parse("2026-10-22T09:00:00.000Z");
const later = (minutes: number) => vi.setSystemTime(T0 + minutes * MINUTE);

const clock = async (route: object, id: string) =>
  (await call(route, "POST", `/v1/tasks/${id}/x`, { params: { id } })).body as ClocksReply;
const move = (board: string, id: string, column: string) =>
  call(cardRoute, "PATCH", `/v1/boards/${board}/cards/${id}`, {
    params: { id: board, taskId: id },
    body: { column_id: column, position: 0 },
  });
const automate = (board: string, automations: StopwatchAutomations) =>
  call(boardStickerRoute, "PATCH", `/v1/boards/${board}/stickers/stopwatch`, {
    params: { id: board, stickerId: "stopwatch" },
    body: { automations },
  });
const stopwatchOf = async (id: string) =>
  ((await call(taskRoute, "GET", `/v1/tasks/${id}`, { params: { id } })).body as ClocksReply).stopwatch;

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(T0);
  resetDemo();
});
afterEach(() => vi.useRealTimers());

describe("the stopwatch", () => {
  it("counts time per column across moves, and starting or stopping twice changes nothing", async () => {
    await clock(stopwatchStartRoute, "w-ai-summaries");
    await clock(stopwatchStartRoute, "w-ai-summaries");
    later(30);
    await move("work", "w-ai-summaries", "planned");
    later(80);
    const stopped = await clock(stopwatchStopRoute, "w-ai-summaries");
    await clock(stopwatchStopRoute, "w-ai-summaries");
    expect(stopped.stopwatch).toEqual({
      running_since: null,
      total_ms: 80 * MINUTE,
      by_column: { ideas: 30 * MINUTE, planned: 50 * MINUTE },
    });
    expect((await clock(stopwatchResetRoute, "w-ai-summaries")).stopwatch).toBeNull();
  });

  it("restarts on a move and stops when done, as the board's automations say", async () => {
    later(10);
    await move("work", "w-ai-summaries", "building");
    expect((await stopwatchOf("w-ai-summaries"))?.running_since).toBe(new Date(T0 + 10 * MINUTE).toISOString());
    later(40);
    await move("work", "w-ai-summaries", "shipped");
    expect(await stopwatchOf("w-ai-summaries")).toMatchObject({
      running_since: null,
      by_column: { building: 30 * MINUTE },
    });
  });

  it("starts on arrival only where the board asks, and never on a board that hides it", async () => {
    await automate("work", { start_on_arrival: true, restart_on_move: false, stop_on_done: true });
    const made = await call(cardsRoute, "POST", "/v1/boards/work/cards", {
      params: { id: "work" },
      body: { title: "Fresh", column_id: "ideas", position: 0 },
    });
    expect((made.body as ClocksReply).stopwatch?.running_since).not.toBeNull();
    await move("work", "w-csv-export", "planned");
    expect(await stopwatchOf("w-csv-export")).toBeNull();
    const home = demo().boards.get("home");
    const column = home?.columns[0]?.id ?? "";
    const there = await call(cardsRoute, "POST", "/v1/boards/home/cards", {
      params: { id: "home" },
      body: { title: "Quiet", column_id: column, position: 0 },
    });
    expect((there.body as ClocksReply).stopwatch).toBeNull();
  });

  it("is refused on a Jira task", async () => {
    const task = demo().tasks.get("w-ai-summaries");
    if (task) task.jira = { key: "WEB-1", url: "https://acme.atlassian.net/browse/WEB-1", type: "Task" };
    const reply = await call(stopwatchStartRoute, "POST", "/v1/tasks/w-ai-summaries/stopwatch/start", {
      params: { id: "w-ai-summaries" },
    });
    expect(codeOf(reply)).toBe("jira_unsupported");
    const pause = await call(timerPauseRoute, "POST", "/v1/tasks/w-ai-summaries/timer/pause", {
      params: { id: "w-ai-summaries" },
    });
    expect(codeOf(pause)).toBe("jira_unsupported");
  });

  it("is never a field of a Jira board", async () => {
    const work = demo().boards.get("work");
    if (!work) throw new Error("no work board");
    const jira = { site: "acme.atlassian.net", project_key: "WEB", board_id: 1, board_name: "WEB", board_url: "" };
    demo().boards.set("jb", {
      ...structuredClone(work),
      id: "jb",
      jira: { ...jira, sync_status: "synced", sync_error: null, last_synced_at: new Date(T0).toISOString() },
    });
    const read = await call(boardRoute, "GET", "/v1/boards/jb", { params: { id: "jb" } });
    expect((read.body as BoardDetail).stickers.map((s) => s.id)).not.toContain("stopwatch");
    const show = await call(boardStickerRoute, "PATCH", "/v1/boards/jb/stickers/timer", {
      params: { id: "jb", stickerId: "timer" },
      body: { visible: true },
    });
    expect(codeOf(show)).toBe("jira_unsupported");
  });
});

describe("the timer", () => {
  const set = (id: string, length_ms: number) =>
    call(timerRoute, "PUT", `/v1/tasks/${id}/timer`, { params: { id }, body: { length_ms } });

  it("pauses, resumes and keeps counting past zero", async () => {
    await set("w-ai-summaries", 60 * MINUTE);
    later(10);
    expect((await clock(timerPauseRoute, "w-ai-summaries")).timer?.paused_left_ms).toBe(50 * MINUTE);
    later(40);
    const resumed = await clock(timerResumeRoute, "w-ai-summaries");
    expect(resumed.timer?.ends_at).toBe(new Date(T0 + 90 * MINUTE).toISOString());
    later(100);
    expect((await clock(timerPauseRoute, "w-ai-summaries")).timer?.paused_left_ms).toBe(-10 * MINUTE);
  });

  it("refuses a length out of range, and pausing a timer that isn't there", async () => {
    expect((await set("w-ai-summaries", 1_000)).status).toBe(422);
    const pause = await call(timerPauseRoute, "POST", "/v1/tasks/w-ai-summaries/timer/pause", {
      params: { id: "w-ai-summaries" },
    });
    expect(codeOf(pause)).toBe("timer_not_set");
  });
});

describe("plan and fact", () => {
  it("are minutes on the task, cleared by null, never negative", async () => {
    const patch = (body: object) =>
      call(taskRoute, "PATCH", "/v1/tasks/w-ai-summaries", { params: { id: "w-ai-summaries" }, body });
    expect(((await patch({ plan_minutes: 240, fact_minutes: 90 })).body as ClocksReply).time_tracking).toEqual({
      plan_minutes: 240,
      fact_minutes: 90,
    });
    expect(((await patch({ plan_minutes: null, fact_minutes: null })).body as ClocksReply).time_tracking).toBeNull();
    expect((await patch({ fact_minutes: -5 })).status).toBe(422);
  });
});
