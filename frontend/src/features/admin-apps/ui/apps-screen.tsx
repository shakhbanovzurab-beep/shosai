"use client";

import { useState } from "react";

import { Upload } from "lucide-react";

import { LoadError } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type { ResourceState } from "@/lib/polling-resource";

import { APP_PLATFORMS, type ReleasesResponse } from "../domain/contract";
import { formatBytes } from "../domain/format";
import { releasesResource, useReleases } from "../model/apps-store";
import { useFileDrop } from "./file-drop";
import { PlatformCard } from "./platform-card";
import { ReleasesHistory } from "./releases-history";
import { UploadSheet } from "./upload-sheet";

type UploadState = { open: boolean; file: File | null; session: number };

export function AppsScreen() {
  const state = useReleases();
  const [upload, setUpload] = useState<UploadState>({ open: false, file: null, session: 0 });
  const ready = state.status === "ready";

  const openUpload = (file: File | null) => setUpload((u) => ({ open: true, file, session: u.session + 1 }));
  // Files dropped anywhere on the page open the upload panel; while it is open, its own drop zone takes them.
  const drop = useFileDrop((file) => openUpload(file), ready && !upload.open);

  return (
    <div className="relative flex flex-col gap-6" {...drop.handlers}>
      <div className="flex flex-col items-start gap-4 sm:flex-row sm:justify-between">
        <div className="flex flex-col gap-1">
          <h1 className="text-3xl tracking-tight">Приложения</h1>
          <p className="text-muted-foreground text-sm">
            Сборки Leo для macOS и Windows: загрузка, публикация и поэтапная раскатка обновлений.
          </p>
        </div>
        <div className="flex flex-col items-start gap-1 sm:items-end">
          <Button size="sm" disabled={!ready} onClick={() => openUpload(null)}>
            <Upload data-icon="inline-start" />
            Загрузить сборку
          </Button>
          {ready ? (
            <span className="text-muted-foreground text-xs">
              До {formatBytes(state.data.max_upload_bytes)} · можно перетащить файл на страницу
            </span>
          ) : null}
        </div>
      </div>

      <ScreenBody state={state} />

      {ready ? (
        <UploadSheet
          key={upload.session}
          open={upload.open}
          onOpenChange={(open) => setUpload((u) => ({ ...u, open }))}
          initialFile={upload.file}
          releases={state.data.releases}
          maxBytes={state.data.max_upload_bytes}
        />
      ) : null}

      {drop.isDragging ? (
        <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center rounded-xl border-2 border-primary border-dashed bg-background/80">
          <p className="font-medium text-sm">Отпустите файл, чтобы загрузить новую сборку</p>
        </div>
      ) : null}
    </div>
  );
}

/** Skeletons while loading, a retryable error, or the platform cards and the history. */
function ScreenBody({ state }: { state: ResourceState<ReleasesResponse> }) {
  if (state.status === "loading")
    return (
      <div className="flex flex-col gap-6" aria-busy="true">
        <p className="sr-only">Загрузка сборок…</p>
        <div className="grid gap-4 lg:grid-cols-2">
          <Skeleton className="h-80 rounded-xl" />
          <Skeleton className="h-80 rounded-xl" />
        </div>
        <Skeleton className="h-96 rounded-xl" />
      </div>
    );
  if (state.status === "error")
    return (
      <LoadError
        title="Не удалось загрузить сборки"
        message={state.message}
        onRetry={() => void releasesResource.refresh()}
        retryLabel="Повторить"
      />
    );
  return (
    <>
      <div className="grid gap-4 lg:grid-cols-2">
        {APP_PLATFORMS.map((platform) => (
          <PlatformCard key={platform} platform={platform} releases={state.data.releases} />
        ))}
      </div>
      <ReleasesHistory releases={state.data.releases} />
    </>
  );
}
