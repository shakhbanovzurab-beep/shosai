import { NEW_BOARD_SYSTEM_VISIBILITY } from "../../domain/stickers-contract";
import type { KanbanDemo, StoredBoard, StoredColumn, StoredTask } from "../store/types";
import {
  assignee,
  DIEGO,
  ELENA,
  fromMeeting,
  inDays,
  MAYA,
  ME_PERSON,
  seedColumn,
  seedComment,
  seedSubtasks,
  seedTask,
} from "./builders";

/*
 * Доски «Home» и «Romashka» и задачи встреч, которые ещё не легли ни на одну доску: они появятся на доске
 * входящих, когда человек её выберет (TK-D4).
 */

const home = {
  todo: [
    seedTask("h-plants", "Water the plants", "", {
      due_on: inDays(0),
      recurrence: { every: "week", weekdays: ["sat", "wed"] },
    }),
    seedTask("h-rent", "Pay the rent", "", {
      priority: "high",
      due_on: inDays(9),
      recurrence: { every: "month", day: 1 },
    }),
    seedTask("h-vacation", "Plan the vacation", "Flights, the hotel and a day in the mountains.", {
      starts_on: inDays(12),
      due_on: inDays(16),
    }),
  ],
  doing: [seedTask("h-dentist", "Book the dentist", "", { status: "in_progress", due_on: inDays(1) })],
  done: [seedTask("h-passport", "Renew the passport", "", { status: "done" })],
} satisfies Record<string, StoredTask[]>;

const romashka = {
  backlog: [seedTask("r-brand-audit", "Brand audit", "")],
  todo: [
    seedTask("r-landing", "Landing page copy", "", { priority: "medium", due_on: inDays(5), assignee: assignee(MAYA) }),
  ],
  progress: [
    seedTask("r-catalog", "Catalog prototype", "", {
      status: "in_progress",
      due_on: inDays(-3),
      assignee: assignee(DIEGO),
    }),
  ],
  review: [seedTask("r-logo", "Logo options", "", { status: "in_progress", assignee: assignee(ELENA) })],
  done: [seedTask("r-kickoff", "Kick-off call", "", { status: "done" })],
} satisfies Record<string, StoredTask[]>;

const hiring = "Hiring sync";
const offsite = "Team offsite planning";
/** Задачи встреч человека, ещё не на доске. */
const unplaced = [
  seedTask("m-hiring-plan", "Share the Q4 hiring plan with Elena", "", {
    due_on: inDays(4),
    assignee: assignee(ME_PERSON),
    leo_fields: ["assignee", "due"],
    source: fromMeeting("m-hiring-sync", hiring, 2, "I'll share the hiring plan with Elena before Monday.", 1_530_000),
  }),
  seedTask("m-venue", "Book the venue for the offsite", "", {
    priority: "high",
    due_on: inDays(7),
    leo_fields: ["due", "priority"],
    source: fromMeeting("m-offsite", offsite, 3, "The venue is urgent, it has to be booked this week.", 312_000),
  }),
];

function board(id: string, name: string, icon: StoredBoard["icon"], columns: StoredColumn[]): StoredBoard {
  return {
    id,
    name,
    icon,
    created_at: "2026-09-01T09:00:00.000Z",
    jira: null,
    syncUntil: null,
    revision: 1,
    columns,
    system: { ...NEW_BOARD_SYSTEM_VISIBILITY, recurrence: id === "home" },
    stickers: [],
  };
}

export function seedPersonalBoards(demo: KanbanDemo) {
  for (const task of [...Object.values(home).flat(), ...Object.values(romashka).flat(), ...unplaced])
    demo.tasks.set(task.id, task);
  demo.subtasks.set(
    "h-vacation",
    seedSubtasks("h-vacation", [
      ["Flights", true],
      ["Hotel", false],
      ["Car rental", false],
    ]),
  );
  demo.comments.set("r-catalog", [seedComment("r-catalog-c1", DIEGO, "Waiting for the product photos.", 2880)]);
  demo.boards.set(
    "home",
    board("home", "Home", "home", [
      seedColumn("home-todo", "To do", "todo", null, home.todo),
      seedColumn("home-doing", "Doing", "in_progress", "amber", home.doing),
      seedColumn("home-done", "Done", "done", null, home.done),
    ]),
  );
  demo.boards.set(
    "romashka",
    board("romashka", "Romashka", "rocket", [
      seedColumn("r-backlog", "Backlog", "todo", null, romashka.backlog),
      seedColumn("r-todo", "To do", "todo", null, romashka.todo),
      seedColumn("r-progress", "In progress", "in_progress", null, romashka.progress),
      seedColumn("r-review", "Review", "in_progress", "violet", romashka.review),
      seedColumn("r-done", "Done", "done", null, romashka.done),
    ]),
  );
}
