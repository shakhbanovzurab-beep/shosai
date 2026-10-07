"use client";

import { useState } from "react";

import { GitCompare, History, RotateCcw } from "lucide-react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";

import type { PlatformPromptVersion } from "../domain/contract";
import { formatDateTime } from "../domain/format";
import { usePlatformPrompts } from "../model/platform-prompts-provider";
import { CompareDialog } from "./compare-dialog";

function VersionRow({ version, onRestore }: { version: PlatformPromptVersion; onRestore: () => void }) {
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
        <p className="break-words text-sm">{version.comment}</p>
        <p className="text-muted-foreground text-xs">
          {version.author} · <time dateTime={version.published_at}>{formatDateTime(version.published_at)}</time>
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

/** Published versions, newest first, with comparison and rollback. */
export function VersionsSection() {
  const {
    state: { versions },
    actions: { restore },
    meta: { hasUnpublishedChanges },
  } = usePlatformPrompts();
  const [target, setTarget] = useState<PlatformPromptVersion | null>(null);

  return (
    <Card className="shadow-xs">
      <CardHeader>
        <CardTitle>История публикаций</CardTitle>
        <CardDescription>Откат публикует копию выбранной версии как новую — история не переписывается.</CardDescription>
      </CardHeader>
      <CardContent>
        {versions.length === 0 ? (
          <Empty className="border border-dashed">
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <History />
              </EmptyMedia>
              <EmptyTitle>Опубликованных версий пока нет</EmptyTitle>
              <EmptyDescription>Опубликуйте черновик, чтобы он применился ко всем пользователям.</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <ul className="flex flex-col divide-y" aria-label="Версии">
            {versions.map((version) => (
              <VersionRow key={version.id} version={version} onRestore={() => setTarget(version)} />
            ))}
          </ul>
        )}
      </CardContent>
      <AlertDialog open={target !== null} onOpenChange={(open) => (open ? undefined : setTarget(null))}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Откатить к версии {target?.number}?</AlertDialogTitle>
            <AlertDialogDescription>
              Её настройки сразу станут действующими для всех пользователей и появятся в истории как новая версия.
              {hasUnpublishedChanges ? " Неопубликованные изменения черновика будут заменены." : null}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Отмена</AlertDialogCancel>
            <AlertDialogAction onClick={() => (target ? void restore(target) : undefined)}>Откатить</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}
