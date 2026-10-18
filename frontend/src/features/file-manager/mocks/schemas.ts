import { z } from "zod";

import { NAME_MAX } from "../domain/contract";
import { type Problem, problem } from "./problems";

// Сообщения схем — коды ошибок бэкенда: ответ отказа берёт их как есть (см. ./problems).
const name = z
  .string()
  .trim()
  .min(1, "name_required")
  .max(NAME_MAX, "name_too_long")
  .refine((value) => !/[/\\]/.test(value), "name_slash");

const ref = z.string().min(1).max(64);

export const registerSchema = z.strictObject({
  upload_ids: z.array(ref).min(1, "upload_count").max(20, "upload_count"),
  folder_id: ref.nullable().optional(),
  leo: z.boolean().optional(),
});

export const fileUpdateSchema = z.strictObject({
  name: name.optional(),
  folder_id: ref.nullable().optional(),
  starred: z.boolean().optional(),
  leo: z.boolean().optional(),
});

export const folderCreateSchema = z.strictObject({ name });

export const folderUpdateSchema = z.strictObject({ name: name.optional(), leo: z.boolean().optional() });

export const uploadSchema = z.strictObject({
  purpose: z.literal("file_manager"),
  filename: z.string().min(1).max(255),
  content_type: z.string().max(255),
  size_bytes: z.number().int().min(1),
});

export const readJson = (request: Request) => request.json().catch(() => null);

const KNOWN = new Set(["name_required", "name_too_long", "name_slash", "upload_count"]);

/** The code a request's first broken rule stands for, as the backend answers it (422). */
export function firstIssue(error: z.ZodError): Problem {
  const message = error.issues[0]?.message ?? "";
  return problem(KNOWN.has(message) ? message : "invalid_request", 422);
}
