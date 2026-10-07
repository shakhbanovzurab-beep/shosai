"use client";

import { useRef, useState } from "react";

import { toast } from "sonner";

import { errorMessage } from "@/lib/errors";

import { appsApi } from "../api/apps-api";
import type { ReleaseMetadata } from "../domain/contract";
import { addRelease } from "./apps-store";
import { fileHash } from "./use-file-hash";

export type UploadPhase =
  | { status: "editing" }
  | { status: "hashing" }
  | { status: "uploading"; loaded: number; total: number }
  | { status: "processing" };

/** Hashes, then uploads a build with progress; `cancel` stops either step. */
export function useUpload(onBusyChange: (busy: boolean) => void, onDone: () => void) {
  const [phase, setPhase] = useState<UploadPhase>({ status: "editing" });
  const [error, setError] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);

  const finish = () => {
    abort.current = null;
    setPhase({ status: "editing" });
    onBusyChange(false);
  };

  const start = async (file: File, metadata: Omit<ReleaseMetadata, "sha256">) => {
    const controller = new AbortController();
    abort.current = controller;
    setError(null);
    onBusyChange(true);
    setPhase({ status: "hashing" });
    const sha256 = await fileHash(file);
    if (controller.signal.aborted) return finish();

    setPhase({ status: "uploading", loaded: 0, total: file.size });
    try {
      const release = await appsApi.upload(
        file,
        { ...metadata, sha256 },
        ({ loaded, total }) =>
          setPhase(loaded >= total ? { status: "processing" } : { status: "uploading", loaded, total }),
        controller.signal,
      );
      addRelease(release);
      toast.success(`Сборка ${release.version} загружена`, { description: "Она сохранена черновиком." });
      finish();
      onDone();
    } catch (e) {
      if (controller.signal.aborted) toast("Загрузка отменена");
      else setError(errorMessage(e) ?? "Не удалось загрузить сборку.");
      finish();
    }
  };

  return {
    phase,
    busy: phase.status !== "editing",
    error,
    clearError: () => setError(null),
    start,
    cancel: () => abort.current?.abort(),
  };
}
