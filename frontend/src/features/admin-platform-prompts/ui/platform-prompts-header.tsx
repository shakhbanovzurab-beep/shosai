"use client";

import { Badge } from "@/components/ui/badge";

import { formatDateTime } from "../domain/format";
import { usePlatformPrompts } from "../model/platform-prompts-provider";
import { PublishDialog } from "./publish-dialog";
import { SaveStatus } from "./save-status";

/** The live version, the draft's save state and the publish action. */
export function PlatformPromptsHeader() {
  const {
    state: { published },
  } = usePlatformPrompts();

  return (
    <div className="flex flex-col gap-3 rounded-xl border bg-card p-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          {published ? (
            <>
              <Badge variant="secondary">Версия {published.number}</Badge>
              <span className="text-muted-foreground">
                опубликована {formatDateTime(published.published_at)} · {published.author}
              </span>
            </>
          ) : (
            <Badge variant="outline">Ещё не опубликовано</Badge>
          )}
        </div>
        <SaveStatus />
      </div>
      <PublishDialog />
    </div>
  );
}
