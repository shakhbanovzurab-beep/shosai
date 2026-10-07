import type {
  PlatformPromptConfig,
  PlatformPromptConfigPatch,
  PlatformPromptDraft,
  PlatformPromptsState,
  PlatformPromptVersion,
} from "../domain/contract";
import { DEMO_AUTHOR, INITIAL_CONFIG } from "./demo-seed";

/* In-memory platform prompts for the demo: one shared draft plus the published versions, newest first. */

type Store = { draft: PlatformPromptDraft; versions: PlatformPromptVersion[] };

const clone = (config: PlatformPromptConfig): PlatformPromptConfig => structuredClone(config);

function seed(): Store {
  const publishedAt = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString();
  const first: PlatformPromptVersion = {
    id: crypto.randomUUID(),
    number: 1,
    config: clone(INITIAL_CONFIG),
    comment: "Первая версия глобальных настроек Leo",
    author: DEMO_AUTHOR,
    published_at: publishedAt,
    restored_from: null,
  };
  return {
    draft: { config: clone(INITIAL_CONFIG), updated_at: publishedAt, updated_by: DEMO_AUTHOR },
    versions: [first],
  };
}

const shared = globalThis as typeof globalThis & { adminDemoPlatformPrompts?: Store };
shared.adminDemoPlatformPrompts ??= seed();
const store = shared.adminDemoPlatformPrompts;

export const getState = (): PlatformPromptsState => ({
  draft: store.draft,
  published: store.versions[0] ?? null,
  versions: store.versions,
});

export function patchDraft(patch: PlatformPromptConfigPatch): PlatformPromptDraft {
  store.draft = {
    config: { ...store.draft.config, ...patch },
    updated_at: new Date().toISOString(),
    updated_by: DEMO_AUTHOR,
  };
  return store.draft;
}

/** Empty guardrail rules and blank topics never reach a published version. */
function cleaned(config: PlatformPromptConfig): PlatformPromptConfig {
  const next = clone(config);
  next.safety.rules = next.safety.rules.filter((rule) => rule.text.trim().length > 0);
  return next;
}

function addVersion(config: PlatformPromptConfig, comment: string, restoredFrom: number | null) {
  const version: PlatformPromptVersion = {
    id: crypto.randomUUID(),
    number: (store.versions[0]?.number ?? 0) + 1,
    config: cleaned(config),
    comment,
    author: DEMO_AUTHOR,
    published_at: new Date().toISOString(),
    restored_from: restoredFrom,
  };
  store.versions = [version, ...store.versions];
  store.draft = { config: clone(version.config), updated_at: version.published_at, updated_by: DEMO_AUTHOR };
}

export function publish(comment: string): PlatformPromptsState {
  addVersion(store.draft.config, comment, null);
  return getState();
}

/** Publishes a copy of an earlier version, so history is never rewritten. Null when the id is unknown. */
export function restore(id: string, comment?: string): PlatformPromptsState | null {
  const source = store.versions.find((version) => version.id === id);
  if (!source) return null;
  addVersion(source.config, comment?.trim() ? comment : `Откат к версии ${source.number}`, source.number);
  return getState();
}
