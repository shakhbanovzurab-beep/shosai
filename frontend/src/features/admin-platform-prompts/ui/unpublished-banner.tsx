"use client";

import { useState } from "react";

import { TriangleAlert } from "lucide-react";

import { ConfirmDestructive } from "@/components/feedback";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

import { usePlatformPrompts } from "../model/platform-prompts-provider";
import { CompareDialog } from "./compare-dialog";

/** Напоминает, что правки доходят до пользователей только после публикации; даёт сравнить или вернуть. */
export function UnpublishedBanner() {
  const {
    state: { published },
    actions: { discardChanges },
    meta: { hasUnpublishedChanges, busy },
  } = usePlatformPrompts();
  const [confirming, setConfirming] = useState(false);

  if (!hasUnpublishedChanges) return null;

  return (
    <Alert role="status" className="border-amber-500/40 bg-amber-500/5">
      <TriangleAlert className="text-amber-600 dark:text-amber-400" aria-hidden="true" />
      <AlertTitle>Есть неопубликованные изменения</AlertTitle>
      <AlertDescription>
        <p>
          {published
            ? `Пользователи пока получают версию ${published.number}. Изменения сохраняются в черновик и применятся после публикации.`
            : "Слой платформы ещё ни разу не публиковался — Leo работает только по своей встроенной политике."}
        </p>
        {published ? (
          <div className="mt-2 flex flex-wrap gap-2">
            <CompareDialog initialLeft={published.id} initialRight="draft">
              <Button size="xs" variant="outline">
                Посмотреть изменения
              </Button>
            </CompareDialog>
            <Button size="xs" variant="ghost" disabled={busy} onClick={() => setConfirming(true)}>
              Отменить изменения
            </Button>
          </div>
        ) : null}
      </AlertDescription>
      <ConfirmDestructive
        open={confirming}
        title="Отменить изменения черновика?"
        description={`Черновик вернётся к опубликованной версии ${published?.number ?? ""}. Несохранённые правки будут потеряны.`}
        confirmLabel="Отменить изменения"
        cancelLabel="Оставить"
        onConfirm={() => void discardChanges()}
        onCancel={() => setConfirming(false)}
      />
    </Alert>
  );
}
