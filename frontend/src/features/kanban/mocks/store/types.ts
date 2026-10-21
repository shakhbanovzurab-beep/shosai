import type { BoardIcon, JiraLink } from "../../domain/board";
import type { ColumnHead } from "../../domain/boards-contract";
import type { CustomSticker, StickerValue, SystemStickerId } from "../../domain/stickers-contract";
import type {
  Assignee,
  Attachment,
  JiraIssueRef,
  LeoField,
  Person,
  Priority,
  Recurrence,
  Subtask,
  TaskSource,
  TaskSpace,
  TaskStatus,
} from "../../domain/tasks-contract";

/*
 * Как моки хранят задачи и доски: так же, как бэкенд по плану tasks (§3.4, §3.8) — одна задача на все доски,
 * место на доске отдельно, поля у владельца, значения у задачи.
 */

export type StoredTask = {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: Priority | null;
  starts_on: string | null;
  due_on: string | null;
  assignee: Assignee | null;
  /** Задача пространства: её заголовок, статус, срок и исполнитель живут в моках пространства. */
  space: TaskSpace | null;
  recurrence: Recurrence | null;
  cover_attachment_id: string | null;
  leo_fields: LeoField[];
  source: TaskSource;
  jira: JiraIssueRef | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  recurred_from_id: string | null;
};

/** Колонка с порядком карточек — то же, что строки размещения задач на доске. */
export type StoredColumn = ColumnHead & { card_ids: string[] };

export type StoredBoard = {
  id: string;
  name: string;
  icon: BoardIcon;
  created_at: string;
  jira: JiraLink | null;
  /** Пока идёт синхронизация Jira — когда она закончится. */
  syncUntil: number | null;
  revision: number;
  columns: StoredColumn[];
  /** Видимость четырёх системных полей. */
  system: Record<SystemStickerId, boolean>;
  /** Свои поля на доске, по порядку. */
  stickers: { id: string; visible: boolean }[];
};

export type StoredComment = { id: string; author: Person; body: string; created_at: string; edited_at: string | null };

export type KanbanDemo = {
  tasks: Map<string, StoredTask>;
  boards: Map<string, StoredBoard>;
  stickers: Map<string, CustomSticker>;
  /** Значения полей: задача → поле → значение (KG-D4: значение — часть задачи). */
  values: Map<string, Map<string, StickerValue>>;
  subtasks: Map<string, Subtask[]>;
  comments: Map<string, StoredComment[]>;
  attachments: Map<string, Attachment[]>;
  /** Доска для входящих задач (TK-D4), null — пока не выбрана. */
  incoming: { board_id: string | null };
};
