import type { ModelCapability, StudioRole } from "./contract";

/**
 * A role the assistant plays. Its name, description and "?" hint (where the role shows up and what its prompt
 * controls) are words, keyed by the role's id in the `studio` catalog (`roles.<id>.name|description|help`).
 */
export type RoleDefinition = {
  id: StudioRole;
  /** What a model must be able to do to fill the role. */
  requires: ModelCapability;
  /** Transcription runs on a speech model and takes no prompt. */
  usesPrompt: boolean;
};

export const ROLES: RoleDefinition[] = [
  { id: "live_answers", requires: "text", usesPrompt: true },
  { id: "screenshots", requires: "vision", usesPrompt: true },
  { id: "code", requires: "text", usesPrompt: true },
  { id: "system_design", requires: "text", usesPrompt: true },
  { id: "notes", requires: "text", usesPrompt: true },
  { id: "transcript", requires: "speech_to_text", usesPrompt: false },
];

/** Roles that take a prompt (Transcript runs on a speech model and doesn't). */
export const PROMPT_ROLES = ROLES.filter((role) => role.usesPrompt);

export const roleById = (id: StudioRole) => ROLES.find((role) => role.id === id);
