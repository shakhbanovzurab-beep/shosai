import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "@/lib/api/errors";

import type { TaskDetail, TodayTask } from "../domain/tasks-contract";

const api = vi.hoisted(() => ({
  tasksApi: {
    today: vi.fn<(day: string) => Promise<{ items: TodayTask[] }>>(),
    create: vi.fn<(body: object, key: string) => Promise<TodayTask>>(),
    patch: vi.fn<(id: string, body: object) => Promise<TodayTask>>(),
  },
}));
type Action = { label: string; onClick: () => void };
const toasts = vi.hoisted(() => ({
  toast: {
    success: vi.fn<(message: string, options: { action?: Action }) => void>(),
    error: vi.fn<(message: string, options: object) => void>(),
  },
}));

vi.mock("../api/tasks-api", () => api);
vi.mock("sonner", () => toasts);

const { addTodayTask, setTodayDone, todayResource } = await import("./today");
type Words = Parameters<typeof addTodayTask>[2];

const said = (key: string) => key;
const words = { kanban: said, today: said, api: said, common: said } as unknown as Words;

const task = (id: string, change: Partial<TodayTask> = {}): TodayTask => ({
  id,
  title: `Задача ${id}`,
  status: "todo",
  starts_on: null,
  due_on: "2026-10-23",
  recurring: false,
  leo_fields: [],
  ...change,
});
const detail = (row: TodayTask) => ({ ...row, description: "" }) as unknown as TaskDetail & TodayTask;

async function listed(day: string, items: TodayTask[]) {
  api.tasksApi.today.mockResolvedValueOnce({ items });
  await todayResource(day).refresh();
}

const shown = (day: string) => {
  const state = todayResource(day).getSnapshot();
  return state.status === "ready" ? state.data.map((row) => [row.id, row.status]) : state.status;
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Today", () => {
  it("adds a personal task due that day, sent once per key, and shows it at once", async () => {
    await listed("2026-10-20", [task("a")]);
    api.tasksApi.create.mockResolvedValueOnce(detail(task("b", { due_on: "2026-10-20" })));

    await addTodayTask("2026-10-20", "Позвонить", words);

    const [body, key] = api.tasksApi.create.mock.calls[0];
    expect(body).toEqual({ title: "Позвонить", description: "", status: "todo", due_on: "2026-10-20" });
    expect(key).toMatch(/^[0-9a-f-]{36}$/);
    expect(shown("2026-10-20")).toEqual([
      ["a", "todo"],
      ["b", "todo"],
    ]);
  });

  it("ticks a task off at once, saves it, and its Undo puts back the status it had", async () => {
    await listed("2026-10-21", [task("a", { status: "in_progress" })]);
    api.tasksApi.patch.mockResolvedValueOnce(detail(task("a", { status: "done" })));

    const ticking = setTodayDone("2026-10-21", task("a", { status: "in_progress" }), true, words);
    expect(shown("2026-10-21")).toEqual([["a", "done"]]);
    await ticking;

    const [message, options] = toasts.toast.success.mock.calls[0];
    expect([message, api.tasksApi.patch.mock.calls[0]]).toEqual(["markedDone", ["a", { status: "done" }]]);
    api.tasksApi.patch.mockResolvedValueOnce(detail(task("a", { status: "in_progress" })));
    options.action?.onClick();
    await vi.waitFor(() => expect(shown("2026-10-21")).toEqual([["a", "in_progress"]]));
    expect(api.tasksApi.patch.mock.calls[1]).toEqual(["a", { status: "in_progress" }]);
  });

  it("puts a refused tick back and says why", async () => {
    await listed("2026-10-22", [task("a")]);
    api.tasksApi.patch.mockRejectedValueOnce(new ApiError("not found", 404, "task_not_found", null));

    await setTodayDone("2026-10-22", task("a"), true, words);

    expect(shown("2026-10-22")).toEqual([["a", "todo"]]);
    expect(toasts.toast.error.mock.calls[0]).toEqual(["errors.saveChange", { description: "task_not_found" }]);
    expect(toasts.toast.success).not.toHaveBeenCalled();
  });

  it("reads Today again after a recurring task's tick, whose next one may fall that day, and offers no Undo", async () => {
    const recurring = task("a", { recurring: true });
    await listed("2026-10-23", [recurring]);
    api.tasksApi.patch.mockResolvedValueOnce(detail({ ...recurring, status: "done", recurring: false }));
    api.tasksApi.today.mockResolvedValueOnce({ items: [task("a", { status: "done" }), task("next")] });

    await setTodayDone("2026-10-23", recurring, true, words);

    await vi.waitFor(() =>
      expect(shown("2026-10-23")).toEqual([
        ["a", "done"],
        ["next", "todo"],
      ]),
    );
    expect(toasts.toast.success.mock.calls[0][1].action).toBeUndefined();
  });

  it("unticks a done task without a toast", async () => {
    await listed("2026-10-24", [task("a", { status: "done" })]);
    api.tasksApi.patch.mockResolvedValueOnce(detail(task("a")));

    await setTodayDone("2026-10-24", task("a", { status: "done" }), false, words);

    expect(shown("2026-10-24")).toEqual([["a", "todo"]]);
    expect(toasts.toast.success).not.toHaveBeenCalled();
  });
});
