import type { CustomSticker, StickerValue } from "./stickers-contract";

/*
 * Задача, как её видят доска и панель: маршруты `/v1/tasks/*` плана tasks (§3.3) и TK-D12 (§3.8).
 * snake_case, ошибки — коды ADR 0008 (`problems.ts`), страницы — `{items, next_cursor}`.
 */

export const TASK_STATUSES = ["todo", "in_progress", "done"] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

/** От самого срочного; приоритета может не быть (KG-D6). */
export const PRIORITIES = ["high", "medium", "low"] as const;
export type Priority = (typeof PRIORITIES)[number];

/** Поля, которые Лео заполнил из встречи и человек ещё не менял (KG-D10). */
export const LEO_FIELDS = ["assignee", "due", "priority"] as const;
export type LeoField = (typeof LEO_FIELDS)[number];

export const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
export type Weekday = (typeof WEEKDAYS)[number];

export type Recurrence = { every: "day" } | { every: "week"; weekdays: Weekday[] } | { every: "month"; day: number };

/** В пространстве — участник (`user_id`); у личной задачи — имя, как его написали. */
export type Assignee = { user_id: string | null; name: string };
export type Cover = { attachment_id: string; preview_url: string | null };
/** Пространство задачи; `workspace_slug` — его адрес в кабинете (`/app/w/{slug}`). */
export type TaskSpace = { workspace_id: string; workspace_slug: string; workspace_name: string };
export type JiraIssueRef = { key: string; url: string; type: string };
export type Person = { user_id: string; name: string };

/** Карточка в чтении доски: только то, что нужно лицу карточки. */
export type Card = {
  id: string;
  title: string;
  status: TaskStatus;
  priority: Priority | null;
  /** Календарные дни "2026-10-20"; начало — только вместе со сроком и не позже него. */
  starts_on: string | null;
  due_on: string | null;
  assignee: Assignee | null;
  cover: Cover | null;
  /** Значения своих полей этой доски. */
  values: Record<string, StickerValue>;
  subtasks_done: number;
  subtasks_total: number;
  comment_count: number;
  attachment_count: number;
  recurring: boolean;
  leo_fields: LeoField[];
  space: TaskSpace | null;
  jira: JiraIssueRef | null;
  /** Может ли человек удалить задачу: свою — да, задачу пространства — её владелец и админы (TK-D2). */
  can_delete: boolean;
};

export type Subtask = { id: string; title: string; done: boolean };

export type Attachment = {
  id: string;
  name: string;
  content_type: string;
  size_bytes: number;
  image: boolean;
  /** Превью картинки не шире 640 px; null, пока его делают. */
  preview_url: string | null;
  added_by: Person;
  added_at: string;
};

export type Comment = {
  id: string;
  author: Person & { is_you: boolean };
  body: string;
  created_at: string;
  edited_at: string | null;
};
export type CommentsPage = { items: Comment[]; next_cursor: string | null };

export type TaskSourceKind = "manual" | "meeting" | "hub" | "mail" | "jira";
export type TaskSource = {
  kind: TaskSourceKind;
  /** Встреча, из которой задача; null, если её нет или она удалена. */
  meeting: { id: string; title: string; started_at: string } | null;
  finding: { quote: string; start_ms: number } | null;
};

export type TaskDetail = Card & {
  description: string;
  recurrence: Recurrence | null;
  /** Значения полей, которых нет на доске читающего, с их определениями (KG-D4). */
  other_values: { sticker: CustomSticker; value: StickerValue }[];
  source: TaskSource;
  subtasks: Subtask[];
  attachments: Attachment[];
  placement: { board_id: string; column_id: string } | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
};

/** Изменение по присутствию поля: `null` очищает. */
export type TaskPatch = {
  title?: string;
  description?: string;
  status?: TaskStatus;
  priority?: Priority | null;
  starts_on?: string | null;
  due_on?: string | null;
  assignee_id?: string | null;
  assignee_name?: string | null;
  recurrence?: Recurrence | null;
  cover_attachment_id?: string | null;
};

export type TasksDelete = { task_ids: string[] };
export type SubtaskCreate = { title: string; position?: number };
export type SubtaskPatch = { title?: string; done?: boolean; position?: number };
export type CommentCreate = { body: string };
export type CommentPatch = { body: string };
/** Загрузка с назначением `task_attachment` или копия файла из File Manager (FL-D4). */
export type AttachmentCreate = { upload_id: string } | { file_id: string };
export type DownloadLink = { url: string; expires_at: string };

export const TITLE_MAX = 200;
export const DESCRIPTION_MAX = 10_000;
export const COMMENT_MAX = 5_000;
export const SUBTASKS_MAX = 100;
export const ATTACHMENTS_MAX = 50;
export const ASSIGNEE_NAME_MAX = 80;
/** Предел одной загрузки вложения; копия файла ограничена только местом. */
export const ATTACHMENT_UPLOAD_MAX = 25 * 1024 * 1024;
export const COMMENTS_PAGE_MAX = 100;
export const COMMENTS_PAGE_DEFAULT = 50;
