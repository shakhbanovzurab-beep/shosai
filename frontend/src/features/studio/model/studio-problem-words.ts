import type { ReactNode } from "react";

import { apiErrorDescription } from "@/lib/api/error-description";

import { STUDIO_ROLES } from "../domain/contract";
import { numberParam, type StudioProblem, studioProblemOf } from "../domain/studio-problems";
import type { StudioApiWords, StudioWords } from "./words";

export type ProblemWords = { api: StudioApiWords; studio: StudioWords };

const roleOf = (value: unknown) => STUDIO_ROLES.find((role) => role === value);

/** Слова отказа studio на языке человека. */
function wordsOf({ code, params }: StudioProblem, { api, studio }: ProblemWords): string {
  switch (code) {
    case "prompt_limit_reached":
      return api(code, { max: numberParam(params, "max") });
    case "prompt_over_budget":
      return api(code, { tokens: numberParam(params, "tokens"), max: numberParam(params, "max") });
    case "max_tokens_range":
      return api(code, { min: numberParam(params, "min"), max: numberParam(params, "max") });
    case "model_cant_do_role": {
      const role = roleOf(params.role);
      return api(code, { model: String(params.model ?? ""), role: role ? studio(`roles.${role}.name`) : "" });
    }
    default:
      return api(code);
  }
}

/** Описание ошибки для тоста: слова studio для известного кода, иначе текст сервера с id запроса. */
export function describeStudioError(error: unknown, words: ProblemWords): ReactNode {
  const problem = studioProblemOf(error);
  return problem === null ? apiErrorDescription(error) : wordsOf(problem, words);
}
