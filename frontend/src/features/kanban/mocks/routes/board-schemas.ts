import { z } from "zod";

import { BOARD_ICONS, BOARD_NAME_MAX, BOARD_TEMPLATE_IDS, COLUMN_KINDS } from "../../domain/board";
import { COLORS } from "../../domain/stickers-contract";
import { PRIORITIES, TITLE_MAX } from "../../domain/tasks-contract";

/* Тела запросов досок, колонок и карточек; сообщение проверки — код отказа, который назовёт кабинет. */

const name = z.string().trim().min(1, "name_required").max(BOARD_NAME_MAX, "name_too_long");
export const title = z.string().trim().min(1, "title_required").max(TITLE_MAX, "title_too_long");
const columnTitle = z.string().trim().min(1, "title_required").max(BOARD_NAME_MAX, "title_too_long");
export const id = z.string().min(1).max(100);
const position = z.int().min(0);
const color = z.enum(COLORS).nullable();

export const boardCreateSchema = z.strictObject({
  name,
  icon: z.enum(BOARD_ICONS),
  template: z.enum(BOARD_TEMPLATE_IDS as [string, ...string[]]),
});
export const boardPatchSchema = z.strictObject({ name: name.optional(), icon: z.enum(BOARD_ICONS).optional() });
export const incomingSchema = z.strictObject({ board_id: id.nullable() });
export const layoutSchema = z.strictObject({
  columns: z.array(z.strictObject({ id, title: columnTitle, task_ids: z.array(id) })).max(20),
});

export const cardCreateSchema = z.strictObject({ title, column_id: id, position, copy_of: id.optional() });
export const cardPatchSchema = z
  .strictObject({
    title: title.optional(),
    priority: z.enum(PRIORITIES).nullable().optional(),
    column_id: id.optional(),
    position: position.optional(),
  })
  // Перемещение передаёт оба поля; иначе запрос неверен.
  .refine((p) => (p.column_id === undefined) === (p.position === undefined));

export const columnCreateSchema = z.strictObject({
  title: columnTitle,
  kind: z.enum(COLUMN_KINDS),
  position,
  color: color.optional(),
});
export const columnPatchSchema = z.strictObject({
  title: columnTitle.optional(),
  color: color.optional(),
  collapsed: z.boolean().optional(),
  position: position.optional(),
});

export const jiraConnectSchema = z.strictObject({ site: z.string().min(1).max(200), board_id: z.int().positive() });
