import { type Prompt, type PromptDraft, type PromptsResponse, STUDIO_ROLES, type StudioRole } from "../domain/contract";
import type { Problem } from "./problems";

/*
 * In-memory stand-in for the user's prompts, used when BACKEND_API_URL is unset. On globalThis so
 * every route bundle shares it; resets when the server restarts.
 */

type State = { prompts: Map<string, Prompt>; active: Record<StudioRole, string | null> };

const shared = globalThis as typeof globalThis & { studioDemoPromptStore?: State };
shared.studioDemoPromptStore ??= {
  prompts: new Map(),
  active: Object.fromEntries(STUDIO_ROLES.map((role) => [role, null])) as Record<StudioRole, string | null>,
};
const state = shared.studioDemoPromptStore;

const now = () => new Date().toISOString();

/** Newest first. */
export const listPrompts = (): PromptsResponse => ({
  prompts: [...state.prompts.values()].toSorted((a, b) => b.updated_at.localeCompare(a.updated_at)),
  active: state.active,
});

export function createPrompt(draft: PromptDraft): Prompt {
  const prompt: Prompt = { id: crypto.randomUUID(), ...draft, updated_at: now() };
  state.prompts.set(prompt.id, prompt);
  return prompt;
}

/** Edits a prompt; moving it to another role stops it being the old role's prompt. `null` if missing. */
export function updatePrompt(id: string, draft: Partial<PromptDraft>): Prompt | null {
  const prompt = state.prompts.get(id);
  if (!prompt) return null;
  if (draft.role && draft.role !== prompt.role && state.active[prompt.role] === id) state.active[prompt.role] = null;
  const next = { ...prompt, ...draft, updated_at: now() };
  state.prompts.set(id, next);
  return next;
}

export function deletePrompt(id: string): boolean {
  const prompt = state.prompts.get(id);
  if (!prompt) return false;
  if (state.active[prompt.role] === id) state.active[prompt.role] = null;
  return state.prompts.delete(id);
}

/** Sets or clears the prompt a role plays by. Returns why it was refused, or null on success. */
export function setActive(role: StudioRole, promptId: string | null): Problem | null {
  if (promptId !== null) {
    const prompt = state.prompts.get(promptId);
    if (!prompt) return { code: "promptNotFound" };
    if (prompt.role !== role) return { code: "promptForOtherRole" };
  }
  state.active[role] = promptId;
  return null;
}
