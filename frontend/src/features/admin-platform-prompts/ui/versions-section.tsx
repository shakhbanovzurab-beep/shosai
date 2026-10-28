"use client";

import { useState } from "react";

import { History } from "lucide-react";

import { LoadError } from "@/components/feedback";
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
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { errorMessage } from "@/lib/errors";

import type { VersionSummary } from "../domain/contract";
import { usePlatformPrompts } from "../model/platform-prompts-provider";
import { useVersions } from "../model/versions";
import { VersionRow } from "./version-row";

function NoVersions() {
  return (
    <Empty className="border border-dashed">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <History />
        </EmptyMedia>
        <EmptyTitle>Опубликованных версий пока нет</EmptyTitle>
        <EmptyDescription>Опубликуйте черновик, чтобы слой платформы дошёл до Leo.</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}

/** История публикаций, новые сверху, страницами; сравнение и откат. */
export function VersionsSection() {
  const {
    actions: { restore },
    meta: { hasUnpublishedChanges },
  } = usePlatformPrompts();
  const history = useVersions();
  const [target, setTarget] = useState<VersionSummary | null>(null);

  return (
    <Card className="shadow-xs">
      <CardHeader>
        <CardTitle>История публикаций</CardTitle>
        <CardDescription>Откат публикует копию выбранной версии как новую — история не переписывается.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {history.isPending ? <Skeleton className="h-40 rounded-lg" role="status" aria-label="Загрузка версий" /> : null}
        {history.isError ? (
          <LoadError
            title="Не удалось загрузить версии"
            message={errorMessage(history.error) ?? "Попробуйте ещё раз."}
            onRetry={() => void history.refetch()}
            retryLabel="Повторить"
          />
        ) : null}
        {history.isSuccess && history.versions.length === 0 ? <NoVersions /> : null}
        {history.versions.length > 0 ? (
          <ul className="flex flex-col divide-y" aria-label="Версии">
            {history.versions.map((version) => (
              <VersionRow key={version.id} version={version} onRestore={() => setTarget(version)} />
            ))}
          </ul>
        ) : null}
        {history.hasNextPage ? (
          <Button
            variant="outline"
            size="sm"
            className="self-center"
            disabled={history.isFetchingNextPage}
            onClick={() => void history.fetchNextPage()}
          >
            {history.isFetchingNextPage ? <Spinner data-icon="inline-start" /> : null}
            Показать ещё
          </Button>
        ) : null}
      </CardContent>
      <AlertDialog open={target !== null} onOpenChange={(open) => (open ? undefined : setTarget(null))}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Откатить к версии {target?.number}?</AlertDialogTitle>
            <AlertDialogDescription>
              Её настройки станут действующими для всех пользователей в течение минуты и появятся в истории как новая
              версия.
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
