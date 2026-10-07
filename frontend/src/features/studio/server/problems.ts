import { getTranslations } from "next-intl/server";

import { detail } from "@/server/backend-proxy";

import type { StudioRole } from "../domain/contract";

/*
 * Why the demo refuses a request, kept as data until the answer goes out. It is then worded in the
 * request's interface language (the `studioApi` catalog), as the backend answers in the language it is asked in.
 */

export type Problem =
  | {
      code:
        | "invalidRequest"
        | "unknownRole"
        | "modelNotOnPlan"
        | "promptNameRequired"
        | "promptNotFound"
        | "promptForOtherRole"
        | "skillNotFound"
        | "skillReferenceInvalid"
        | "skillFileEmpty"
        | "repositoryInvalid"
        | "directoryUnavailable";
    }
  | { code: "contextTooLong" | "promptNameTooLong" | "promptTooLong" | "tooManySkills"; max: number }
  | { code: "maxTokensRange"; min: number; max: number }
  | { code: "modelCantDoRole"; model: string; role: StudioRole }
  | { code: "skillMissing"; path: string; repository: string }
  | { code: "repositoryUnreadable" | "repositoryNoSkills"; repository: string };

export const isProblem = (value: object): value is Problem => "code" in value;

/** The words for a problem in the request's interface language. */
async function word(problem: Problem): Promise<string> {
  const t = await getTranslations("studioApi");
  switch (problem.code) {
    case "contextTooLong":
    case "promptNameTooLong":
    case "promptTooLong":
    case "tooManySkills":
      return t(problem.code, { max: problem.max });
    case "maxTokensRange":
      return t(problem.code, { min: problem.min, max: problem.max });
    case "modelCantDoRole": {
      const roles = await getTranslations("studio");
      return t(problem.code, { model: problem.model, role: roles(`roles.${problem.role}.name`) });
    }
    case "skillMissing":
      return t(problem.code, { path: problem.path, repository: problem.repository });
    case "repositoryUnreadable":
    case "repositoryNoSkills":
      return t(problem.code, { repository: problem.repository });
    default:
      return t(problem.code);
  }
}

/** A refusal in FastAPI's shape, `{ "detail": message }`, in the request's interface language. */
export async function refuse(problem: Problem, status: number) {
  return detail(await word(problem), status);
}
