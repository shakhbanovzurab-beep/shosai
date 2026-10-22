import type { Card, LeoField, TaskDetail, TaskPatch } from "./tasks-contract";

/* Правила задачи, общие для панели и моков. */

/** Какие метки Лео остаются после изменения (KG-D10): поле, которое человек поменял, метку теряет. */
export function leoFieldsAfter(leo: LeoField[], patch: TaskPatch): LeoField[] {
  const changed = new Set<LeoField>();
  if (patch.assignee_id !== undefined || patch.assignee_name !== undefined) changed.add("assignee");
  if (patch.due_on !== undefined || patch.starts_on !== undefined) changed.add("due");
  if (patch.priority !== undefined) changed.add("priority");
  return leo.filter((field) => !changed.has(field));
}

/** Счётчики карточки из списков задачи: прогресс подзадач и число вложений идут за панелью сразу. */
export function withCounts(detail: TaskDetail): TaskDetail {
  const done = detail.subtasks.filter((subtask) => subtask.done).length;
  return {
    ...detail,
    subtasks_done: done,
    subtasks_total: detail.subtasks.length,
    attachment_count: detail.attachments.length,
  };
}

/** Список, где элемент `id` стоит на месте `to` (как `position` в API: место после того, как его вынули). */
export function movedTo<T extends { id: string }>(list: T[], id: string, to: number): T[] {
  const from = list.findIndex((item) => item.id === id);
  if (from < 0) return list;
  const rest = list.toSpliced(from, 1);
  return rest.toSpliced(Math.min(Math.max(0, to), rest.length), 0, list[from]);
}

/** Карточка из задачи целиком: поля, которые видит доска. */
export function cardOf(detail: TaskDetail): Card {
  const {
    description: _description,
    recurrence: _recurrence,
    other_values: _other,
    source: _source,
    subtasks: _subtasks,
    attachments: _attachments,
    placement: _placement,
    created_at: _created,
    updated_at: _updated,
    completed_at: _completed,
    server_now: _now,
    ...card
  } = detail;
  return card;
}
