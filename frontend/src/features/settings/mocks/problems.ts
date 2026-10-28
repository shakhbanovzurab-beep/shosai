import type { z } from "zod";

import { detail, getTranslations } from "@/mocks/runtime";

import type { ComboProblem } from "../domain/hotkeys";

/*
 * Why the demo refuses a request, kept as a code until the answer goes out. It is then worded in the
 * request's interface language (the `settingsApi` catalog), as the backend answers in the language it is asked in.
 */

export type Problem =
  | "invalidRequest"
  | "nameRequired"
  | "hotkeyUnsupported"
  | "modelNotOnPlan"
  | "emailMismatch"
  | "deletionUnavailable"
  | "avatarMissing"
  | "avatarType"
  | "paymentsUnavailable"
  | "checkoutUnavailable"
  | "invoiceNotFound"
  | "dataKindUnknown"
  | "dataItemNotFound"
  | "mcpNameRequired"
  | "mcpNameTooLong"
  | "mcpUrlInvalid"
  | "mcpServerNotFound";

/** The words for a problem in the request's interface language. */
export async function problemText(problem: Problem) {
  const t = await getTranslations("settingsApi");
  return t(`problems.${problem}`);
}

/** A refusal in FastAPI's shape, `{ "detail": message }`, in the request's interface language. */
export async function refuse(problem: Problem, status: number) {
  return detail(await problemText(problem), status);
}

/** A shortcut that can't be saved, worded as Settings › Hotkeys words it. */
export async function refuseCombo(problem: ComboProblem) {
  const t = await getTranslations("settingsHotkeys");
  const text =
    problem.code === "taken"
      ? t("problems.taken", { command: t(`commands.${problem.owner}`) })
      : t(`problems.${problem.code}`);
  return detail(text, 422);
}

/**
 * What to tell the user about an invalid body: the schemas' messages are problem codes for what the user
 * can fix (`.min(1, "nameRequired")`); anything else is a malformed request.
 */
export function firstIssue(error: z.ZodError, fixable: readonly Problem[]): Problem {
  const message = error.issues[0]?.message ?? "";
  return fixable.find((problem) => problem === message) ?? "invalidRequest";
}

export const readJson = (request: Request) => request.json().catch(() => null);
