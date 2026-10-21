import type { StickerValue } from "../../domain/stickers-contract";
import type { KanbanDemo, StoredBoard, StoredTask } from "../store/types";
import {
  assignee,
  DIEGO,
  ELENA,
  fromMeeting,
  gradientPreview,
  inDays,
  MAYA,
  ME_PERSON,
  seedAttachment,
  seedColumn,
  seedComment,
  seedSubtasks,
  seedTask,
} from "./builders";

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

function threads(demo: KanbanDemo) {
  demo.subtasks.set(
    "w-schema",
    seedSubtasks("w-schema", [
      ["Parties and employees", true],
      ["Tenders and work orders", true],
      ["Indexes for search", false],
    ]),
  );
  demo.subtasks.set(
    "w-sso-crash",
    seedSubtasks("w-sso-crash", [
      ["Reproduce", true],
      ["Fix the redirect", false],
    ]),
  );
  demo.comments.set("w-schema", [
    seedComment("w-schema-c1", MAYA, "Should work orders keep their history?", 300),
    seedComment("w-schema-c2", ME_PERSON, "Yes, as a separate table. See https://orm.drizzle.team", 240),
  ]);
  demo.comments.set("w-sso-crash", [seedComment("w-sso-crash-c1", ELENA, "Only with the Okta tenant so far.", 90)]);
  demo.attachments.set("w-schema", [
    seedAttachment("w-schema-a1", "schema.png", 412_000, ME_PERSON, gradientPreview("#6366f1", "#0ea5e9")),
    seedAttachment("w-schema-a2", "Data model.pdf", 1_240_000, MAYA, null),
  ]);
  demo.attachments.set("w-sso-crash", [
    seedAttachment("w-sso-crash-a1", "safari-console.png", 230_000, ELENA, gradientPreview("#f43f5e", "#f59e0b")),
  ]);
}

export function seedWorkBoard(demo: KanbanDemo) {
  stickers(demo);
  for (const task of Object.values(tasks).flat()) demo.tasks.set(task.id, task);
  for (const [task, sticker, value] of VALUES) {
    const values = demo.values.get(task) ?? new Map<string, StickerValue>();
    demo.values.set(task, values.set(sticker, value));
  }
  threads(demo);
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
    system: { assignee: true, due: true, priority: true, recurrence: true },
    stickers: [
      { id: TYPE, visible: true },
      { id: ESTIMATE, visible: true },
      { id: CUSTOMER, visible: false },
    ],
  };
  demo.boards.set(board.id, board);
}
