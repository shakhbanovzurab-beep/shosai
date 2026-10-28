"use client";

import { Badge } from "@/components/ui/badge";

import { formatDateTime } from "../domain/format";
import { usePlatformPrompts } from "../model/platform-prompts-provider";
import { PublishDialog } from "./publish-dialog";
import { SaveStatus } from "./save-status";

/** Действующая версия, состояние черновика и публикация. */
export function PlatformPromptsHeader() {
  const {
    state: { published },
    meta: { publishBlocker },
  } = usePlatformPrompts();

  return (
    <div className="flex flex-col gap-3 rounded-xl border bg-card p-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {published ? (
            <>
              <Badge variant="secondary">Версия {published.number}</Badge>
              <span className="text-muted-foreground">опубликована {formatDateTime(published.published_at)}</span>
            </>
          ) : (
            <Badge variant="outline">Ещё не опубликовано</Badge>
          )}
        </div>
        <SaveStatus />
        {publishBlocker ? (
          <p className="text-destructive text-xs" role="status">
            Опубликовать нельзя: {publishBlocker}
          </p>
        ) : null}
      </div>
      <PublishDialog />
    </div>
  );
}
