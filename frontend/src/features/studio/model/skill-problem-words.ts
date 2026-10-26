import type { ReactNode } from "react";

import { apiErrorDescription } from "@/lib/api/error-description";

import { skillProblemOf } from "../domain/skill-problems";
import type { SkillWords } from "./words";

/** A refusal of the skills store in the user's words; any other error as the server said it, with its request id. */
export function describeSkillError(error: unknown, t: SkillWords): ReactNode {
  const problem = skillProblemOf(error);
  return problem === null ? apiErrorDescription(error) : t(`problems.${problem}`);
}
