"use client";

import { createContext, type ReactNode, use, useState } from "react";

import { sameConfig } from "../domain/config-diff";
import type { PlatformPromptConfig, PlatformPromptsState, PlatformPromptVersion } from "../domain/contract";
import { configPatchSchema } from "../domain/schema";
import { persist, publishDraft, resetDraft, restoreVersion } from "./platform-prompts-actions";
import { platformPromptsResource } from "./platform-prompts-store";
import { type AutosaveStatus, useDraftAutosave } from "./use-draft-autosave";

type PlatformPromptsContextValue = {
  state: {
    /** The draft as edited here; saved to the server automatically. */
    config: PlatformPromptConfig;
    published: PlatformPromptVersion | null;
    versions: PlatformPromptVersion[];
    draftUpdatedAt: string;
    /** Bumped whenever the draft is replaced from outside (publish, rollback, discard), to reset local inputs. */
    revision: number;
  };
  actions: {
    update: (change: (config: PlatformPromptConfig) => PlatformPromptConfig) => void;
    retrySave: () => void;
    publish: (comment: string) => Promise<boolean>;
    restore: (version: PlatformPromptVersion) => Promise<boolean>;
    discardChanges: () => Promise<boolean>;
  };
  meta: {
    saveStatus: AutosaveStatus;
    saveError: string | null;
    /** Why the draft can't be saved as it stands, e.g. a prompt over its limit; null when it is valid. */
    invalidReason: string | null;
    hasUnpublishedChanges: boolean;
    busy: boolean;
  };
};

const PlatformPromptsContext = createContext<PlatformPromptsContextValue | null>(null);

export function usePlatformPrompts() {
  const value = use(PlatformPromptsContext);
  if (!value) throw new Error("usePlatformPrompts must be used inside PlatformPromptsProvider.");
  return value;
}

/** Owns the editable draft for the whole screen; sections read and change it through `usePlatformPrompts`. */
export function PlatformPromptsProvider({ data, children }: { data: PlatformPromptsState; children: ReactNode }) {
  const [config, setConfig] = useState(data.draft.config);
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const autosave = useDraftAutosave(persist);

  const validation = configPatchSchema.safeParse(config);
  const invalidReason = validation.success ? null : (validation.error.issues[0]?.message ?? "Проверьте поля.");

  const replace = (state: PlatformPromptsState) => {
    platformPromptsResource.update(() => state);
    setConfig(state.draft.config);
    setRevision((value) => value + 1);
  };

  const update: PlatformPromptsContextValue["actions"]["update"] = (change) => {
    const next = change(config);
    setConfig(next);
    // An invalid draft stays local until it is fixed; the server would refuse it anyway.
    if (configPatchSchema.safeParse(next).success) autosave.schedule(next);
  };

  /** Runs one server action with the busy flag set, then swaps in the state it returns. */
  const runExclusive = (action: () => Promise<PlatformPromptsState | null>) => {
    setBusy(true);
    return action()
      .finally(() => setBusy(false))
      .then((next) => {
        if (next) replace(next);
        return next !== null;
      });
  };

  const publish = (comment: string) => runExclusive(() => publishDraft(autosave.flush, comment));
  const restore = (version: PlatformPromptVersion) => runExclusive(() => restoreVersion(autosave.discard, version));
  const discardChanges = () => runExclusive(() => resetDraft(autosave.discard, data));

  const value: PlatformPromptsContextValue = {
    state: {
      config,
      published: data.published,
      versions: data.versions,
      draftUpdatedAt: data.draft.updated_at,
      revision,
    },
    actions: { update, retrySave: () => void autosave.flush(), publish, restore, discardChanges },
    meta: {
      saveStatus: autosave.status,
      saveError: autosave.error,
      invalidReason,
      hasUnpublishedChanges: !sameConfig(config, data.published?.config),
      busy,
    },
  };

  return <PlatformPromptsContext value={value}>{children}</PlatformPromptsContext>;
}
