"use client";

import { GitCompare, RotateCcw } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import type { VersionSummary } from "../domain/contract";
import { formatDateTime } from "../domain/format";
import { usePlatformPrompts } from "../model/platform-prompts-provider";
import { CompareDialog } from "./compare-dialog";

/** Одна версия истории: номер, комментарий, время; сравнение с черновиком и откат к ней. */
export function VersionRow({ version, onRestore }: { version: VersionSummary; onRestore: () => void }) {
  const {
    state: { published },
    meta: { busy },
  } = usePlatformPrompts();
  const live = published?.id === version.id;

  return (
    <li className="flex flex-col gap-3 py-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium text-sm">Версия {version.number}</span>
          {live ? <Badge>Опубликована</Badge> : null}
          {version.restored_from === null ? null : (
            <Badge variant="outline">Откат к версии {version.restored_from}</Badge>
          )}
        </div>
        {version.comment ? <p className="break-words text-sm">{version.comment}</p> : null}
        <p className="text-muted-foreground text-xs">
          <time dateTime={version.published_at}>{formatDateTime(version.published_at)}</time>
        </p>
      </div>
      <div className="flex shrink-0 gap-2">
        <CompareDialog initialLeft={version.id} initialRight="draft">
          <Button size="sm" variant="outline" aria-label={`Сравнить версию ${version.number} с черновиком`}>
            <GitCompare data-icon="inline-start" />
            Сравнить
          </Button>
        </CompareDialog>
        <Button
          size="sm"
          variant="outline"
          disabled={live || busy}
          onClick={onRestore}
          aria-label={`Откатить к версии ${version.number}`}
        >
          <RotateCcw data-icon="inline-start" />
          Откатить
        </Button>
      </div>
    </li>
  );
}
