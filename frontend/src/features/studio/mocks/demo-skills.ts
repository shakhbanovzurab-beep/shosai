import type { Skill } from "../domain/contract";
import { loadSkill } from "./github-skills";
import { isProblem, type Problem } from "./problems";

/*
 * In-memory stand-in for installed skills, used when BACKEND_API_URL is unset. Installing and
 * updating really read the skill from GitHub; only storage is fake. Resets on server restart.
 */

const shared = globalThis as typeof globalThis & { studioDemoSkills?: Map<string, Skill> };
shared.studioDemoSkills ??= new Map<string, Skill>();
const store = shared.studioDemoSkills;

export const listSkills = (): Skill[] => [...store.values()].toSorted((a, b) => a.name.localeCompare(b.name));

/** Installs a skill, or returns the existing one if that folder is already installed. */
export async function installSkill(reference: string): Promise<Skill | Problem> {
  const loaded = await loadSkill(reference);
  if (isProblem(loaded)) return loaded;
  const existing = [...store.values()].find((s) => s.reference === loaded.reference);
  if (existing) return existing;
  const skill: Skill = { id: crypto.randomUUID(), ...loaded, updated_at: new Date().toISOString() };
  store.set(skill.id, skill);
  return skill;
}

/** Re-reads the skill from GitHub at its latest commit. `null` if it isn't installed. */
export async function updateSkill(id: string): Promise<Skill | Problem | null> {
  const skill = store.get(id);
  if (!skill) return null;
  const loaded = await loadSkill(skill.reference);
  if (isProblem(loaded)) return loaded;
  const next: Skill = { ...skill, ...loaded, updated_at: new Date().toISOString() };
  store.set(id, next);
  return next;
}

export const uninstallSkill = (id: string) => store.delete(id);
