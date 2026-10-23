import type { components } from "@/lib/api/generated/schema";

/*
 * Задача, как её видят доска и панель: маршруты `/v1/tasks/*` плана tasks (§3.3) и TK-D12 (§3.8). Формы — из
 * сгенерированного контракта бэкенда (`openapi.json`); здесь их имена в языке слайса и пределы, которые проверяет
 * экран. Ошибки — коды ADR 0008 (`problems.ts`).
 */

type Schemas = components["schemas"];

export type TaskStatus = Schemas["TaskStatus"];
export const TASK_STATUSES = ["todo", "in_progress", "done"] as const satisfies readonly TaskStatus[];

/** От самого срочного; приоритета может не быть (KG-D6). */
export type Priority = Schemas["Priority"];
export const PRIORITIES = ["high", "medium", "low"] as const satisfies readonly Priority[];

/** Поля, которые Лео заполнил из встречи и человек ещё не менял (KG-D10). */
export type LeoField = Schemas["LeoField"];
export const LEO_FIELDS = ["assignee", "due", "priority"] as const satisfies readonly LeoField[];

export type Weekday = Schemas["Weekday"];
export const WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const satisfies readonly Weekday[];

export type Recurrence = Schemas["Recurrence"];

/** В пространстве — участник (`user_id`); у личной задачи — имя, как его написали. */
export type Assignee = Schemas["AssigneeOut"];
export type Cover = Schemas["CoverOut"];
/** Пространство задачи; `workspace_slug` — его адрес в кабинете (`/app/w/{slug}`). */
export type TaskSpace = Schemas["SpaceOut"];
export type JiraIssueRef = Schemas["JiraOut"];
export type Person = Schemas["PersonOut"];

/** Карточка в чтении доски: только то, что нужно лицу карточки. */
export type Card = Schemas["Card"];
export type Subtask = Schemas["SubtaskOut"];
/** Превью картинки не шире 640 px; null, пока его делают. */
export type Attachment = Schemas["AttachmentOut"];
export type Comment = Schemas["CommentOut"];
export type CommentsPage = Schemas["Page_CommentOut_"];

export type TaskSourceKind = Schemas["TaskSource"];
/** Мессенджеры командных чатов (chats §1.1). */
export type ChatMessenger = Schemas["Messenger"];
export type CardChatSource = Schemas["ChatLineOut"];
/**
 * Чат и сообщение, из которых задача (TK-D13): как были при создании, поэтому строка переживает отключение
 * чата; подключения тогда уже нет (`connection_id` null), а ссылка ведёт в мессенджер.
 */
export type TaskChatSource = Schemas["ChatSourceOut"];
export type TaskSource = Schemas["SourceOut"];

/** Задача в панели: карточка, описание, источник, чек-лист, вложения и момент ответа сервера (ADR 0061). */
export type TaskDetail = Schemas["TaskDetail"];

/** Строка списка Today (TK-D11): ровно то, что показывает виджет; панель и ответ создания тоже её несут. */
export type TodayTask = Pick<
  Schemas["TaskItem"],
  "id" | "title" | "status" | "starts_on" | "due_on" | "recurring" | "leo_fields"
>;
export type TodayList = Schemas["TodayOut"];
export type TaskCreate = Schemas["TaskCreateBody"];

/** Изменение по присутствию поля: `null` очищает. */
export type TaskPatch = Schemas["TaskPatchBody"];
export type TasksDelete = Schemas["TasksDeleteBody"];
export type SubtaskCreate = Schemas["SubtaskCreateBody"];
export type SubtaskPatch = Schemas["SubtaskPatchBody"];
export type CommentCreate = Schemas["CommentBody"];
export type CommentPatch = Schemas["CommentBody"];
/** Загрузка с назначением `task_attachment` или копия файла из File Manager (FL-D4). */
export type AttachmentCreate = Schemas["UploadSourceBody"] | Schemas["FileSourceBody"];
export type DownloadLink = Schemas["AttachmentDownloadOut"];

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
