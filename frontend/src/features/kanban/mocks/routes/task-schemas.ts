import { z } from "zod";

import {
  COLORS,
  CUSTOM_KINDS,
  STATE_NAME_MAX,
  STATES_MAX,
  STICKER_NAME_MAX,
  STICKER_TEXT_MAX,
} from "../../domain/stickers-contract";
import {
  ASSIGNEE_NAME_MAX,
  COMMENT_MAX,
  DESCRIPTION_MAX,
  PRIORITIES,
  TASK_STATUSES,
  WEEKDAYS,
} from "../../domain/tasks-contract";
import { id, title } from "./board-schemas";

/* Тела запросов задачи, её подзадач, комментариев, вложений и полей. */

const day = z.string().regex(/^\d{4}-\d{2}-\d{2}$/);
const recurrence = z.discriminatedUnion("every", [
  z.strictObject({ every: z.literal("day") }),
  z.strictObject({ every: z.literal("week"), weekdays: z.array(z.enum(WEEKDAYS)).min(1).max(7) }),
  z.strictObject({ every: z.literal("month"), day: z.int().min(1).max(31) }),
]);

export const taskPatchSchema = z.strictObject({
  title: title.optional(),
  description: z.string().max(DESCRIPTION_MAX, "description_too_long").optional(),
  status: z.enum(TASK_STATUSES).optional(),
  priority: z.enum(PRIORITIES).nullable().optional(),
  starts_on: day.nullable().optional(),
  due_on: day.nullable().optional(),
  assignee_id: id.nullable().optional(),
  assignee_name: z.string().trim().min(1).max(ASSIGNEE_NAME_MAX).nullable().optional(),
  recurrence: recurrence.nullable().optional(),
  cover_attachment_id: id.nullable().optional(),
});
export const tasksDeleteSchema = z.strictObject({ task_ids: z.array(id).min(1).max(500) });

export const subtaskCreateSchema = z.strictObject({ title, position: z.int().min(0).optional() });
export const subtaskPatchSchema = z.strictObject({
  title: title.optional(),
  done: z.boolean().optional(),
  position: z.int().min(0).optional(),
});

const body = z.string().trim().min(1, "validation_error").max(COMMENT_MAX, "comment_too_long");
export const commentSchema = z.strictObject({ body });

export const attachmentSchema = z.union([z.strictObject({ upload_id: id }), z.strictObject({ file_id: id })]);

const stickerName = z.string().trim().min(1, "name_required").max(STICKER_NAME_MAX, "name_too_long");
const state = z.strictObject({
  id: id.optional(),
  name: z.string().trim().min(1, "name_required").max(STATE_NAME_MAX, "name_too_long"),
  color: z.enum(COLORS),
});
const states = z.array(state).max(STATES_MAX, "states_full");

export const placeStickerSchema = z.union([
  z.strictObject({ sticker_id: id }),
  z.strictObject({ kind: z.enum(CUSTOM_KINDS), name: stickerName, states: states.optional() }),
]);
export const stickerPatchSchema = z.strictObject({ name: stickerName.optional(), states: states.optional() });
export const boardStickerPatchSchema = z.strictObject({ visible: z.boolean() });

export const valueSchema = z.union([
  z.strictObject({ state_id: id }),
  z.strictObject({ number: z.number().finite() }),
  z.strictObject({ text: z.string().trim().min(1).max(STICKER_TEXT_MAX) }),
]);
