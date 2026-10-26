import { ApiError } from "@/lib/api/errors";

/**
 * Why the skills store refused a request: the codes of the backend's `agent` slice for `/v1/agent/skills*`
 * (step 15). The dialog words them in the user's language; any other code keeps the server's text and the
 * request id for support.
 */
export const SKILL_PROBLEMS = [
  "skill_already_installed",
  "skill_limit_reached",
  "skill_not_found",
  "repo_not_found",
  "skill_reference_invalid",
  "repository_invalid",
  "repo_too_large",
  "skill_too_large",
  "no_frontmatter",
  "skill_file_empty",
  "ambiguous_skill",
  "rate_limited",
  "github_unavailable",
  "skills_unavailable",
] as const;

export type SkillProblem = (typeof SKILL_PROBLEMS)[number];

/** The known problem behind an error, or null for anything else. */
export function skillProblemOf(error: unknown): SkillProblem | null {
  if (!(error instanceof ApiError)) return null;
  return SKILL_PROBLEMS.find((problem) => problem === error.code) ?? null;
}
