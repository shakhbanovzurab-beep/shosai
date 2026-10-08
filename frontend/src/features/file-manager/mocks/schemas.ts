import { z } from "zod";

import { NAME_MAX } from "../domain/contract";
import type { Problem } from "./problems";

// Messages are problem codes, worded for the request when it is refused (see ./problems).
type NameProblem = "fileNameRequired" | "folderNameRequired" | "nameTooLong" | "nameSlash";
const NAME_PROBLEMS: readonly string[] = [
  "fileNameRequired",
  "folderNameRequired",
  "nameTooLong",
  "nameSlash",
] satisfies NameProblem[];

const name = (required: NameProblem) =>
  z
    .string()
    .trim()
    .min(1, required)
    .max(NAME_MAX, "nameTooLong" satisfies NameProblem)
    .refine((value) => !/[/\\]/.test(value), "nameSlash" satisfies NameProblem);

const ref = z.string().min(1).max(64);

export const fileUpdateSchema = z.strictObject({
  name: name("fileNameRequired").optional(),
  folder_id: ref.nullable().optional(),
  starred: z.boolean().optional(),
  leo: z.boolean().optional(),
});

export const folderCreateSchema = z.strictObject({ name: name("folderNameRequired") });

export const folderUpdateSchema = z.strictObject({
  name: name("folderNameRequired").optional(),
  leo: z.boolean().optional(),
});

export const transferSchema = z.strictObject({ workspace_id: ref });

export const readJson = (request: Request) => request.json().catch(() => null);

/** What to tell the user about an invalid body: a name they can fix, or that the request is malformed. */
export function firstIssue(error: z.ZodError): Problem {
  const message = error.issues[0]?.message ?? "";
  if (!NAME_PROBLEMS.includes(message)) return { code: "invalidRequest" };
  const code = message as NameProblem;
  return code === "nameTooLong" ? { code, max: NAME_MAX } : { code };
}
