"use client";

import { createContext, type ReactNode, use, useState } from "react";

import { useQueryClient } from "@tanstack/react-query";

import type { PlatformConfig, PlatformPromptsState, PlatformVersion, VersionSummary } from "../domain/contract";
import { BUILT_IN, publishProblem, sameConfig } from "../domain/platform-layer";
import { problemText } from "../domain/problems";
import { configSchema } from "../domain/schema";
import { persist, publishDraft, resetDraft, restoreVersion } from "./platform-prompts-actions";
import { platformPromptsResource } from "./platform-prompts-store";
import { type AutosaveStatus, useDraftAutosave } from "./use-draft-autosave";
import { VERSIONS_KEY } from "./versions";

type PlatformPromptsContextValue = {
  state: {
    /** Черновик в том виде, в каком его правят здесь; сохраняется на сервер сам. */
    config: PlatformConfig;
    published: PlatformVersion | null;
    /** Null — черновик ещё ни разу не сохраняли. */
    draftUpdatedAt: string | null;
    /** Растёт, когда черновик заменён снаружи (публикация, откат, отмена), чтобы поля со своим текстом сбросились. */
    revision: number;
  };
  actions: {
    update: (change: (config: PlatformConfig) => PlatformConfig) => void;
    retrySave: () => void;
    publish: (comment: string) => Promise<boolean>;
    restore: (version: VersionSummary) => Promise<boolean>;
    discardChanges: () => Promise<boolean>;
  };
  meta: {
    saveStatus: AutosaveStatus;
    saveError: string | null;
    /** Почему черновик нельзя сохранить как есть, например промт длиннее лимита; null, если можно. */
    invalidReason: string | null;
    /** Что не даст опубликовать черновик: неанглийский текст или выход за бюджет; null, если ничего. */
    publishBlocker: string | null;
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

/** Держит редактируемый черновик всего экрана; разделы читают и меняют его через `usePlatformPrompts`. */
export function PlatformPromptsProvider({ data, children }: { data: PlatformPromptsState; children: ReactNode }) {
  const queryClient = useQueryClient();
  const [config, setConfig] = useState(data.draft.config);
  const [revision, setRevision] = useState(0);
  const [busy, setBusy] = useState(false);
  const autosave = useDraftAutosave(persist);

  const validation = configSchema.safeParse(config);
  const invalidReason = validation.success ? null : (validation.error.issues[0]?.message ?? "Проверьте поля.");
  const problem = publishProblem(config);

  const replace = (state: PlatformPromptsState) => {
    platformPromptsResource.update(() => state);
    setConfig(state.draft.config);
    setRevision((value) => value + 1);
    void queryClient.invalidateQueries({ queryKey: VERSIONS_KEY });
  };

  const update: PlatformPromptsContextValue["actions"]["update"] = (change) => {
    const next = change(config);
    setConfig(next);
    // Неверный черновик остаётся здесь, пока его не исправят: сервер его всё равно не примет.
    if (configSchema.safeParse(next).success) autosave.schedule(next);
  };

  /** Выполняет одно действие на сервере под флагом занятости и подставляет состояние, которое оно вернуло. */
  const runExclusive = (action: () => Promise<PlatformPromptsState | null>) => {
    setBusy(true);
    return action()
      .finally(() => setBusy(false))
      .then((next) => {
        if (next) replace(next);
        return next !== null;
      });
  };

  const publish = (comment: string) => runExclusive(() => publishDraft(autosave.flush, config, comment));
  const restore = (version: VersionSummary) => runExclusive(() => restoreVersion(autosave.discard, config, version));
  const discardChanges = () => runExclusive(() => resetDraft(autosave.discard, data));

  const value: PlatformPromptsContextValue = {
    state: { config, published: data.published, draftUpdatedAt: data.draft.updated_at, revision },
    actions: { update, retrySave: () => void autosave.flush(), publish, restore, discardChanges },
    meta: {
      saveStatus: autosave.status,
      saveError: autosave.error,
      invalidReason,
      publishBlocker: problem ? problemText(problem, config) : null,
      hasUnpublishedChanges: !sameConfig(config, data.published?.config ?? BUILT_IN),
      busy,
    },
  };

  return <PlatformPromptsContext value={value}>{children}</PlatformPromptsContext>;
}
