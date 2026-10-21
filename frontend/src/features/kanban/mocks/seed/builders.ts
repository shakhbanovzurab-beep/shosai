import { ME } from "@/features/workspace/mocks/demo-people";
import { dayIn } from "@/i18n/calendar-days";
import { cabinetTimeZone } from "@/i18n/time-zone";

import type { ColumnKind } from "../../domain/board";
import { addDays } from "../../domain/recurrence";
import type { Color } from "../../domain/stickers-contract";
import type { Attachment, Person, Subtask, TaskSource } from "../../domain/tasks-contract";
import type { StoredColumn, StoredComment, StoredTask } from "../store/types";

/*
 * Кирпичики демо-данных. Названия задач, колонок и полей — то, что написали люди, поэтому они на одном языке
 * во всех языках интерфейса и передаются позиционно, а не литералами `title:`.
 */

export const ME_PERSON: Person = { user_id: ME.account, name: ME.name };
export const person = (user_id: string, name: string): Person => ({ user_id, name });

export const MAYA = person("u-maya", "Maya Chen");
export const ELENA = person("u-elena", "Elena Petrova");
export const DIEGO = person("u-diego", "Diego Alvarez");

/** Сегодня человека в его поясе. */
export const today = () => dayIn(new Date(), cabinetTimeZone());
export const inDays = (days: number) => addDays(today(), days);
const MINUTE = 60_000;
export const minutesAgo = (minutes: number) => new Date(Date.now() - minutes * MINUTE).toISOString();

export const MANUAL: TaskSource = { kind: "manual", meeting: null, finding: null };

/** Задача из встречи: её исходная встреча и находка с цитатой и моментом. */
export function fromMeeting(
  meetingId: string,
  meeting: string,
  daysAgo: number,
  quote: string,
  atMs: number,
): TaskSource {
  const started_at = new Date(Date.now() - daysAgo * 86_400_000).toISOString();
  return {
    kind: "meeting",
    meeting: { id: meetingId, title: meeting, started_at },
    finding: { quote, start_ms: atMs },
  };
}

export function seedTask(id: string, title: string, description: string, fields: Partial<StoredTask> = {}) {
  const created_at = minutesAgo(60 * 24 * 7);
  const task: StoredTask = {
    id,
    title,
    description,
    status: "todo",
    priority: null,
    starts_on: null,
    due_on: null,
    assignee: null,
    space: null,
    recurrence: null,
    cover_attachment_id: null,
    leo_fields: [],
    source: MANUAL,
    jira: null,
    created_at,
    updated_at: created_at,
    completed_at: null,
    recurred_from_id: null,
    ...fields,
  };
  if (task.status === "done" && !task.completed_at) task.completed_at = minutesAgo(60 * 24);
  return task;
}

export function seedColumn(id: string, title: string, kind: ColumnKind, color: Color | null, cards: StoredTask[]) {
  const column: StoredColumn = { id, title, kind, color, collapsed: false, card_ids: cards.map((task) => task.id) };
  return column;
}

export const assignee = (who: Person) => ({ user_id: null, name: who.name });

export function seedSubtasks(taskId: string, items: [title: string, done: boolean][]): Subtask[] {
  return items.map(([title, done], index) => ({ id: `${taskId}-s${index + 1}`, title, done }));
}

export function seedComment(id: string, author: Person, body: string, ago: number): StoredComment {
  return { id, author, body, created_at: minutesAgo(ago), edited_at: null };
}

/** Превью-обложка без байтов: градиент 640×360 в data URL. */
export function gradientPreview(from: string, to: string) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="360"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${from}"/><stop offset="1" stop-color="${to}"/></linearGradient></defs><rect width="640" height="360" fill="url(#g)"/></svg>`;
  return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

export function seedAttachment(id: string, name: string, size: number, by: Person, preview: string | null): Attachment {
  const image = preview !== null;
  const document = name.endsWith(".pdf") ? "application/pdf" : "application/octet-stream";
  const content_type = image ? "image/png" : document;
  return {
    id,
    name,
    content_type,
    size_bytes: size,
    image,
    preview_url: preview,
    added_by: by,
    added_at: minutesAgo(600),
  };
}
