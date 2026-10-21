/* Общее для досок: виды колонок, иконки, шаблоны, связь с Jira, адрес доски. Формы API — в `*-contract.ts`. */

/** A column's role, the same three categories Jira groups its statuses into. */
export const COLUMN_KINDS = ["todo", "in_progress", "done"] as const;
export type ColumnKind = (typeof COLUMN_KINDS)[number];

/* ---------- Boards ---------- */

export const BOARD_ICONS = [
  "briefcase",
  "home",
  "user",
  "heart",
  "graduation-cap",
  "plane",
  "shopping-cart",
  "dumbbell",
  "rocket",
  "book",
] as const;
export type BoardIcon = (typeof BOARD_ICONS)[number];

export type JiraSyncStatus = "syncing" | "synced" | "error";

/** Where a synced board comes from in Jira, and how the sync is doing. */
export type JiraLink = {
  /** The Jira Cloud site, e.g. "acme.atlassian.net". */
  site: string;
  project_key: string;
  board_id: number;
  board_name: string;
  board_url: string;
  sync_status: JiraSyncStatus;
  /** Код причины, по которой синхронизация остановилась (`reconnect_jira`), или null; кабинет называет его сам. */
  sync_error: string | null;
  last_synced_at: string | null;
};

/** The starting columns a template can have; the screen and the API name them in the user's language. */
export type TemplateColumn = "backlog" | "todo" | "inProgress" | "review" | "done";

/** Starting columns for a new app board. */
export const BOARD_TEMPLATES = {
  simple: [
    { name: "todo", kind: "todo" },
    { name: "inProgress", kind: "in_progress" },
    { name: "done", kind: "done" },
  ],
  project: [
    { name: "backlog", kind: "todo" },
    { name: "todo", kind: "todo" },
    { name: "inProgress", kind: "in_progress" },
    { name: "review", kind: "in_progress" },
    { name: "done", kind: "done" },
  ],
} as const satisfies Record<string, readonly { name: TemplateColumn; kind: ColumnKind }[]>;
export type BoardTemplate = keyof typeof BOARD_TEMPLATES;
export const BOARD_TEMPLATE_IDS = Object.keys(BOARD_TEMPLATES) as BoardTemplate[];

export const BOARD_NAME_MAX = 60;

/** The Kanban page showing a board. */
export const boardHref = (id: string) => `/app/kanban?board=${encodeURIComponent(id)}`;
