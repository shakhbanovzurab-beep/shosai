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
    ...card
  } = detail;
  return card;
}
