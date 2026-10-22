import { NEW_BOARD_SYSTEM_VISIBILITY } from "../../domain/stickers-contract";
import type { Priority, TaskStatus } from "../../domain/tasks-contract";
import { DEFAULT_STOPWATCH_AUTOMATIONS } from "../../domain/time-contract";
import type { KanbanDemo, StoredBoard } from "../store/types";
import { assignee, DIEGO, ELENA, inDays, MAYA, ME_PERSON, seedColumn, seedTask } from "./builders";

/*
 * Большие доски для замеров (план пакета §5.4): 300 и 1 000 открытых карточек. Появляются, только когда в
 * sessionStorage стоит переключатель, чтобы обычное демо оставалось прежним.
 */

export const LARGE_BOARDS_SWITCH = "kanban-demo-large";

export function largeBoardsOn() {
  try {
    return globalThis.sessionStorage?.getItem(LARGE_BOARDS_SWITCH) === "1";
  } catch {
    return false;
  }
}

const PEOPLE = [ME_PERSON, MAYA, ELENA, DIEGO];
const PRIORITIES: (Priority | null)[] = [null, "high", null, "medium", "low", null];
const LANES: [id: string, title: string, status: TaskStatus][] = [
  ["backlog", "Backlog", "todo"],
  ["next", "Next", "todo"],
  ["doing", "Doing", "in_progress"],
  ["review", "Review", "in_progress"],
];

function largeBoard(demo: KanbanDemo, id: string, name: string, cards: number) {
  const lanes = LANES.map(([lane, title, status], laneIndex) => {
    const tasks = Array.from({ length: Math.ceil((cards - laneIndex) / LANES.length) }, (_, i) => {
      const n = i * LANES.length + laneIndex + 1;
      const task = seedTask(`${id}-${n}`, `Task ${n}`, "", {
        status,
        priority: PRIORITIES[n % PRIORITIES.length],
        due_on: n % 3 === 0 ? inDays((n % 20) - 5) : null,
        assignee: n % 4 === 0 ? null : assignee(PEOPLE[n % PEOPLE.length]),
      });
      demo.tasks.set(task.id, task);
      if (n % 2 === 0) demo.values.set(task.id, new Map([["st-estimate", { number: (n % 5) + 1 }]]));
      if (n % 3 === 0) {
        const values = demo.values.get(task.id) ?? new Map();
        demo.values.set(task.id, values.set("st-type", { state_id: n % 2 ? "type-bug" : "type-feature" }));
      }
      return task;
    });
    return seedColumn(`${id}-${lane}`, title, status, null, tasks);
  });
  const board: StoredBoard = {
    id,
    name,
    icon: "rocket",
    created_at: "2026-10-01T09:00:00.000Z",
    jira: null,
    syncUntil: null,
    revision: 1,
    columns: [...lanes, seedColumn(`${id}-done`, "Done", "done", "green", [])],
    system: { ...NEW_BOARD_SYSTEM_VISIBILITY },
    stopwatch: { ...DEFAULT_STOPWATCH_AUTOMATIONS },
    stickers: [
      { id: "st-type", visible: true },
      { id: "st-estimate", visible: true },
    ],
  };
  demo.boards.set(id, board);
}

export function seedLargeBoards(demo: KanbanDemo) {
  largeBoard(demo, "load-300", "Load 300", 300);
  largeBoard(demo, "load-1000", "Load 1000", 1000);
}
