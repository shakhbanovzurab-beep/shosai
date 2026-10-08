import { z } from "zod";

import { BOARD_ICONS, BOARD_NAME_MAX, BOARD_TEMPLATE_IDS, TASK_PRIORITIES, TASK_TITLE_MAX } from "../domain/board";
import type { Problem } from "./problems";

// Messages are problem codes, worded for the request when it is refused (see ./problems).
const VALIDATION_PROBLEMS = ["boardNameRequired", "boardNameTooLong", "taskTitleRequired"] as const satisfies Problem[];
type ValidationProblem = (typeof VALIDATION_PROBLEMS)[number];

const name = z
  .string()
  .trim()
  .min(1, "boardNameRequired" satisfies ValidationProblem)
  .max(BOARD_NAME_MAX, "boardNameTooLong" satisfies ValidationProblem);
const title = z
  .string()
  .trim()
  .min(1, "taskTitleRequired" satisfies ValidationProblem)
  .max(TASK_TITLE_MAX);
const id = z.string().min(1).max(100);

export const createBoardSchema = z.strictObject({
  name,
  icon: z.enum(BOARD_ICONS),
  template: z.enum(BOARD_TEMPLATE_IDS as [string, ...string[]]),
});
export const boardPatchSchema = z.strictObject({ name: name.optional(), icon: z.enum(BOARD_ICONS).optional() });
export const layoutSchema = z.strictObject({
  columns: z
    .array(z.strictObject({ id, title: z.string().trim().min(1).max(BOARD_NAME_MAX), task_ids: z.array(id) }))
    .max(20),
});
export const taskCreateSchema = z.strictObject({
  column_id: id,
  position: z.int().min(0),
  title,
  copy_of: id.optional(),
});
export const taskPatchSchema = z
  .strictObject({
    title: title.optional(),
    priority: z.enum(TASK_PRIORITIES as [string, ...string[]]).optional(),
    column_id: id.optional(),
    position: z.int().min(0).optional(),
  })
  // Moving sends both; anything else is a malformed request.
  .refine((p) => (p.column_id === undefined) === (p.position === undefined));
export const tasksDeleteSchema = z.strictObject({ task_ids: z.array(id).min(1).max(500) });
export const connectJiraSchema = z.strictObject({ site: z.string().min(1).max(200), board_id: z.int().positive() });

export const readJson = (request: Request) => request.json().catch(() => null);
const isValidationProblem = (message: string | undefined): message is ValidationProblem =>
  (VALIDATION_PROBLEMS as readonly string[]).includes(message ?? "");

/** What to tell the user about an invalid body: a problem they can fix, or that the request is malformed. */
export const firstIssue = (error: z.ZodError): Problem => {
  const message = error.issues[0]?.message;
  return isValidationProblem(message) ? message : "invalidRequest";
};

export const workspaceTasksSchema = z.strictObject({ board_id: z.string().min(1).max(64).nullable() });
