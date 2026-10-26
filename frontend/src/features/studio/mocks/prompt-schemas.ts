import { z } from "zod";

import {
  CONTEXT_MAX_CHARS,
  PROMPT_CONTENT_MAX,
  PROMPT_NAME_MAX,
  PROMPT_SKILLS_MAX,
  STUDIO_ROLES,
} from "../domain/contract";
import type { Problem } from "./problems";

// Messages are problem codes, worded for the request when it is refused (see ./problems).
const LIMITS = {
  contextTooLong: CONTEXT_MAX_CHARS,
  promptNameTooLong: PROMPT_NAME_MAX,
  promptTooLong: PROMPT_CONTENT_MAX,
  tooManySkills: PROMPT_SKILLS_MAX,
} as const satisfies Partial<Record<Problem["code"], number>>;
type LimitProblem = keyof typeof LIMITS;
const NAME_REQUIRED = "promptNameRequired" satisfies Problem["code"];

export const promptDraftSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, NAME_REQUIRED)
    .max(PROMPT_NAME_MAX, "promptNameTooLong" satisfies LimitProblem),
  role: z.enum(STUDIO_ROLES),
  content: z
    .string()
    .trim()
    .max(PROMPT_CONTENT_MAX, "promptTooLong" satisfies LimitProblem),
  skill_ids: z.array(z.string().max(100)).max(PROMPT_SKILLS_MAX, "tooManySkills" satisfies LimitProblem),
});

export const contextBodySchema = z.object({
  content: z.string().max(CONTEXT_MAX_CHARS, "contextTooLong" satisfies LimitProblem),
});

export const readJson = (request: Request) => request.json().catch(() => null);

/** What to tell the user about an invalid body: a problem they can fix, or that the request is malformed. */
export function firstIssue(error: z.ZodError): Problem {
  const message = error.issues[0]?.message ?? "";
  if (message === NAME_REQUIRED) return { code: NAME_REQUIRED };
  if (Object.hasOwn(LIMITS, message)) return { code: message as LimitProblem, max: LIMITS[message as LimitProblem] };
  return { code: "invalidRequest" };
}
