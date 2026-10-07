/* The Kanban model: boards with their own columns, synced two-way with Jira or kept in the app. */

/** A column's role, the same three categories Jira groups its statuses into. */
export const COLUMN_KINDS = ["todo", "in_progress", "done"] as const;
export type ColumnKind = (typeof COLUMN_KINDS)[number];

export type Column = { id: string; title: string; kind: ColumnKind };

export type TaskPriority = "High" | "Medium" | "Low";

export type TaskInsightLabel = "Attachments" | "Comments" | "Documents";

export type TaskInsight = { label: TaskInsightLabel; count: number };

/** The colour family of an owner's avatar. */
export type OwnerTone = "zinc" | "lime" | "indigo" | "fuchsia" | "violet" | "pink" | "sky";

export type TaskOwnerProfile = { name: string; tone: OwnerTone };

/** The Jira issue behind a task on a synced board. */
export type JiraIssueRef = { key: string; url: string; type: string };

/**
 * A workspace task assigned to you, shown on the board you picked for them. The card is a view of the
 * workspace's task, not a copy: moving it changes the task's status there, renaming renames it there.
 */
export type WorkspaceTaskRef = {
  workspace_id: string;
  workspace_name: string;
  task_id: string;
  /** Where to open it: the workspace's tasks, or the meeting it came from. */
  url: string;
  /** The project or meeting it came from; null for a task added by hand. */
  source: string | null;
};

export type Task = {
  id: string;
  title: string;
  description: string;
  priority: TaskPriority;
  /** A calendar day, "2026-06-26"; null when there is none. The screen words it in the user's language. */
  dueDate: string | null;
  /** 0–100 for work in progress; null when not tracked. */
  progress: number | null;
  /** Null while unassigned. */
  owner: TaskOwnerProfile | null;
  /** A short tag: the team ("Design") or, on a Jira board, the issue type ("Bug"). */
  label: string | null;
  insights: TaskInsight[];
  /** Set on tasks of a board synced with Jira. */
  jira?: JiraIssueRef;
  /** Set on a card that shows one of your workspace tasks. */
  workspace?: WorkspaceTaskRef;
};

/** Tasks per column id, in display order. */
export type BoardState = Record<string, Task[]>;

/** Priorities from most to least urgent, as the priority menu lists them. */
export const TASK_PRIORITIES: TaskPriority[] = ["High", "Medium", "Low"];

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
  /** Why the last sync failed, e.g. the Jira connection was removed; null otherwise. */
  sync_error: string | null;
  last_synced_at: string | null;
};

export type BoardSummary = {
  id: string;
  name: string;
  icon: BoardIcon;
  /** Null for a board kept in the app; set for a board synced two-way with a Jira board. */
  jira: JiraLink | null;
  /** Whether your tasks from your workspaces show on this board (one app board at a time). */
  receives_workspace_tasks: boolean;
  task_count: number;
  created_at: string;
};

export type BoardDetail = {
  board: BoardSummary;
  columns: Column[];
  tasks: BoardState;
  /** Goes up with every change, including ones that arrive from Jira. */
  revision: number;
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
export const TASK_TITLE_MAX = 200;

/** The Kanban page showing a board. */
export const boardHref = (id: string) => `/app/kanban?board=${encodeURIComponent(id)}`;
