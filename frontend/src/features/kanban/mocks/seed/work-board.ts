import type { StickerValue } from "../../domain/stickers-contract";
import { NEW_BOARD_SYSTEM_VISIBILITY } from "../../domain/stickers-contract";
import { DEFAULT_STOPWATCH_AUTOMATIONS } from "../../domain/time-contract";
import type { KanbanDemo, StoredBoard, StoredTask } from "../store/types";
import { assignee, DIEGO, ELENA, fromMeeting, inDays, MAYA, ME_PERSON, seedColumn, seedTask } from "./builders";
import { chatTasks } from "./work-chats";
import { seedWorkClocks } from "./work-clocks";
import { seedWorkThreads } from "./work-threads";

/* Доска «Work»: поток продуктовой команды со своими полями — тип, оценка в днях и заказчик. */

const ME_OWNS = { user_id: ME_PERSON.user_id };
const TYPE = "st-type";
const ESTIMATE = "st-estimate";
const CUSTOMER = "st-customer";

function stickers(demo: KanbanDemo) {
  demo.stickers.set(TYPE, {
    id: TYPE,
    kind: "states",
    name: "Type",
    owner: ME_OWNS,
    states: [
      { id: "type-feature", name: "Feature", color: "blue" },
      { id: "type-bug", name: "Bug", color: "red" },
      { id: "type-chore", name: "Chore", color: "gray" },
    ],
  });
  demo.stickers.set(ESTIMATE, { id: ESTIMATE, kind: "number", name: "Estimate in days", owner: ME_OWNS, states: [] });
  demo.stickers.set(CUSTOMER, { id: CUSTOMER, kind: "text", name: "Customer", owner: ME_OWNS, states: [] });
}

const pricing = "Pricing review with Lumen";
const fromChats = chatTasks();
const tasks = {
  ideas: [
    seedTask("w-ai-summaries", "AI summaries for long threads", "Summaries of email threads longer than ten messages."),
    seedTask("w-dark-charts", "Charts in the dark theme", ""),
  ],
  planned: [
    seedTask("w-pricing-deck", "Send the pricing deck to Lumen", "", {
      priority: "high",
      due_on: inDays(2),
      assignee: assignee(ME_PERSON),
      leo_fields: ["assignee", "due", "priority"],
      source: fromMeeting("m-lumen-pricing", pricing, 1, "Arham will send the updated deck by Thursday.", 754_000),
    }),
    seedTask("w-onboarding", "Draft the onboarding checklist", "", {
      due_on: inDays(6),
      leo_fields: ["due"],
      source: fromMeeting("m-lumen-pricing", pricing, 1, "Let's have the checklist next week.", 1_212_000),
    }),
    seedTask("w-release-notes", "Weekly release notes", "Collect what shipped and **post it** to the team channel.", {
      due_on: inDays(3),
      recurrence: { every: "week", weekdays: ["fri"] },
      assignee: assignee(ME_PERSON),
    }),
    ...fromChats.planned,
  ],
  building: [
    seedTask("w-schema", "SQLite and Drizzle schema", "Model parties, employees, tenders and work orders.", {
      status: "in_progress",
      priority: "high",
      due_on: inDays(3),
      assignee: assignee(ME_PERSON),
      cover_attachment_id: "w-schema-a1",
    }),
    seedTask("w-salary-import", "Salary Excel import", "Read salary sheets and keep the import batches.", {
      status: "in_progress",
      priority: "medium",
      due_on: inDays(-2),
      assignee: assignee(MAYA),
    }),
    seedTask("w-mapping", "Column mapping builder", "", {
      status: "in_progress",
      starts_on: inDays(-1),
      due_on: inDays(4),
      assignee: assignee(DIEGO),
    }),
    ...fromChats.building,
  ],
  qa: [
    seedTask("w-sso-crash", "Crash on sign-in with SSO", "Reproduced on Safari 18 with the Okta tenant.", {
      status: "in_progress",
      priority: "high",
      due_on: inDays(-1),
      assignee: assignee(ELENA),
      cover_attachment_id: "w-sso-crash-a1",
    }),
    seedTask("w-csv-export", "CSV export of work orders", "", { status: "in_progress", assignee: assignee(MAYA) }),
  ],
  shipped: [
    seedTask("w-tenders", "Tender list filters", "", { status: "done", priority: "low", assignee: assignee(DIEGO) }),
    seedTask("w-ocr", "Document OCR", "", { status: "done", assignee: assignee(ME_PERSON) }),
  ],
} satisfies Record<string, StoredTask[]>;

/** Значение текстового поля — то, что человек написал. */
const typed = (words: string): StickerValue => ({ text: words });

const VALUES: [task: string, sticker: string, value: StickerValue][] = [
  ["w-ai-summaries", TYPE, { state_id: "type-feature" }],
  ["w-pricing-deck", CUSTOMER, typed("Lumen")],
  ["w-schema", TYPE, { state_id: "type-feature" }],
  ["w-schema", ESTIMATE, { number: 4 }],
  ["w-salary-import", TYPE, { state_id: "type-feature" }],
  ["w-salary-import", ESTIMATE, { number: 3 }],
  ["w-mapping", ESTIMATE, { number: 2.5 }],
  ["w-sso-crash", TYPE, { state_id: "type-bug" }],
  ["w-sso-crash", ESTIMATE, { number: 1 }],
  ["w-sso-crash", CUSTOMER, typed("Northwind")],
  ["w-csv-export", TYPE, { state_id: "type-chore" }],
  ["w-tenders", TYPE, { state_id: "type-feature" }],
];

export function seedWorkBoard(demo: KanbanDemo) {
  stickers(demo);
  // Копии, а не сами объекты сида: сброс демо (тесты) начинает с чистых задач.
  for (const task of Object.values(tasks).flat()) demo.tasks.set(task.id, structuredClone(task));
  for (const [task, sticker, value] of VALUES) {
    const values = demo.values.get(task) ?? new Map<string, StickerValue>();
    demo.values.set(task, values.set(sticker, value));
  }
  seedWorkThreads(demo);
  seedWorkClocks(demo);
  const board: StoredBoard = {
    id: "work",
    name: "Work",
    icon: "briefcase",
    created_at: "2026-09-01T09:00:00.000Z",
    jira: null,
    syncUntil: null,
    revision: 1,
    columns: [
      seedColumn("ideas", "Ideas", "todo", null, tasks.ideas),
      seedColumn("planned", "Planned", "todo", "blue", tasks.planned),
      seedColumn("building", "Building", "in_progress", "amber", tasks.building),
      seedColumn("qa", "QA", "in_progress", "violet", tasks.qa),
      seedColumn("shipped", "Shipped", "done", "green", tasks.shipped),
    ],
    // Доска демо показывает и время задачи (ADR 0061): секундомер по колонкам, таймер, план и факт.
    system: { ...NEW_BOARD_SYSTEM_VISIBILITY, recurrence: true, stopwatch: true, timer: true, time_tracking: true },
    stopwatch: { ...DEFAULT_STOPWATCH_AUTOMATIONS },
    stickers: [
      { id: TYPE, visible: true },
      { id: ESTIMATE, visible: true },
      { id: CUSTOMER, visible: false },
    ],
  };
  demo.boards.set(board.id, board);
}
