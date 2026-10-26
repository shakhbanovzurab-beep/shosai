import type { ReactNode } from "react";

import { toast } from "sonner";

import { skillsApi } from "../api/skills-api";
import type { Skill, SkillCandidate } from "../domain/contract";
import { describeSkillError } from "./skill-problem-words";
import { promptsResource, skillsResource } from "./studio-resources";
import type { SkillWords } from "./words";

const replace = (skill: Skill) =>
  skillsResource.update((data) => ({ skills: data.skills.map((s) => (s.id === skill.id ? skill : s)) }));

export async function installSkill(candidate: SkillCandidate, t: SkillWords) {
  try {
    const skill = await skillsApi.install(candidate.reference);
    skillsResource.update((data) => ({
      skills: [...data.skills.filter((s) => s.id !== skill.id), skill],
    }));
    toast.success(t("toasts.installed", { name: skill.name }), { description: t("toasts.installedHint") });
  } catch (error) {
    toast.error(t("toasts.installFailed"), { description: describeSkillError(error, t) });
  }
}

/** Re-reads the skill at the latest commit of its repository. */
export async function updateSkill(skill: Skill, t: SkillWords) {
  try {
    const next = await skillsApi.update(skill.id);
    replace(next);
    toast.success(
      next.commit === skill.commit
        ? t("toasts.upToDate", { name: skill.name })
        : t("toasts.updated", { name: skill.name }),
    );
  } catch (error) {
    toast.error(t("toasts.updateFailed"), { description: describeSkillError(error, t) });
  }
}

export async function uninstallSkill(skill: Skill, t: SkillWords) {
  try {
    await skillsApi.uninstall(skill.id);
    skillsResource.update((data) => ({ skills: data.skills.filter((s) => s.id !== skill.id) }));
    void promptsResource.refresh();
    toast.success(t("toasts.removed", { name: skill.name }));
  } catch (error) {
    toast.error(t("toasts.removeFailed"), { description: describeSkillError(error, t) });
  }
}

export type ScanState = { results: SkillCandidate[] | null; error: ReactNode };

/** Form action: lists the SKILL.md files in the submitted GitHub repository. */
export async function scanRepository(form: FormData, t: SkillWords): Promise<ScanState> {
  try {
    const { results } = await skillsApi.scan(String(form.get("repository") ?? ""));
    return { results, error: null };
  } catch (error) {
    return { results: null, error: describeSkillError(error, t) ?? t("repository.scanFailed") };
  }
}
