"use client";

import { CircleAlert, CircleCheck } from "lucide-react";

import { Spinner } from "@/components/ui/spinner";

import { formatDateTime } from "../domain/format";
import { usePlatformPrompts } from "../model/platform-prompts-provider";

/** Where the draft stands: saving, saved, failed with a retry, or held back because a field is invalid. */
export function SaveStatus() {
  const {
    state: { draftUpdatedAt },
    actions: { retrySave },
    meta: { saveStatus, saveError, invalidReason },
  } = usePlatformPrompts();

  if (invalidReason) {
    return (
      <span className="flex items-center gap-1.5 text-destructive text-xs" role="alert">
        <CircleAlert className="size-3.5 shrink-0" aria-hidden="true" />
        Не сохраняется: {invalidReason}
      </span>
    );
  }
  if (saveStatus === "error") {
    return (
      <span className="flex items-center gap-1.5 text-destructive text-xs" role="alert">
        <CircleAlert className="size-3.5 shrink-0" aria-hidden="true" />
        {saveError ?? "Не удалось сохранить."}
        <button type="button" className="rounded-sm underline underline-offset-2" onClick={retrySave}>
          Повторить
        </button>
      </span>
    );
  }
  if (saveStatus === "saving" || saveStatus === "pending") {
    return (
      <span className="flex items-center gap-1.5 text-muted-foreground text-xs" aria-live="polite">
        <Spinner className="size-3" />
        Сохранение черновика…
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1.5 text-muted-foreground text-xs" aria-live="polite">
      <CircleCheck className="size-3.5 shrink-0" aria-hidden="true" />
      Черновик сохранён {formatDateTime(draftUpdatedAt)}
    </span>
  );
}
