import { toast } from "sonner";

import { errorMessage } from "@/lib/errors";

import { studioApi } from "../api/studio-api";
import type { Skill, SkillCandidate } from "../domain/contract";
import { promptsResource, skillsResource } from "./studio-resources";
import type { SkillWords } from "./words";

const replace = (skill: Skill) =>
  skillsResource.update((data) => ({ skills: data.skills.map((s) => (s.id === skill.id ? skill : s)) }));

export async function installSkill(candidate: SkillCandidate, t: SkillWords) {
  try {
    const skill = await studioApi.installSkill(candidate.reference);
    skillsResource.update((data) => ({
      skills: [...data.skills.filter((s) => s.id !== skill.id), skill],
    }));
    toast.success(t("toasts.installed", { name: skill.name }), { description: t("toasts.installedHint") });
  } catch (error) {
    toast.error(t("toasts.installFailed"), { description: errorMessage(error) });
  }
}

/** Re-reads the skill at the latest commit of its repository. */
export async function updateSkill(skill: Skill, t: SkillWords) {
  try {
    const next = await studioApi.updateSkill(skill.id);
    replace(next);
    toast.success(
      next.commit === skill.commit
        ? t("toasts.upToDate", { name: skill.name })
        : t("toasts.updated", { name: skill.name }),
    );
  } catch (error) {
    toast.error(t("toasts.updateFailed"), { description: errorMessage(error) });
  }
}

export async function uninstallSkill(skill: Skill, t: SkillWords) {
  try {
    await studioApi.uninstallSkill(skill.id);
    skillsResource.update((data) => ({ skills: data.skills.filter((s) => s.id !== skill.id) }));
    void promptsResource.refresh();
    toast.success(t("toasts.removed", { name: skill.name }));
  } catch (error) {
    toast.error(t("toasts.removeFailed"), { description: errorMessage(error) });
  }
}

export type ScanState = { results: SkillCandidate[] | null; error: string | null };

/** Form action: lists the SKILL.md files in the submitted GitHub repository. */
export async function scanRepository(form: FormData, t: SkillWords): Promise<ScanState> {
  try {
    const { results } = await studioApi.scanRepository(String(form.get("repository") ?? ""));
    return { results, error: null };
  } catch (error) {
    return { results: null, error: errorMessage(error) ?? t("repository.scanFailed") };
  }
}
