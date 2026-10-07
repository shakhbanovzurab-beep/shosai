"use client";

import { useState } from "react";

import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";

import type { AppRelease } from "../domain/contract";
import { formatBytes } from "../domain/format";
import { UploadForm } from "./upload-form";

type UploadSheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initialFile: File | null;
  releases: readonly AppRelease[];
  maxBytes: number;
};

/** The upload panel. It can't be dismissed mid-upload; the form's «Отменить загрузку» stops it first. */
export function UploadSheet({ open, onOpenChange, initialFile, releases, maxBytes }: UploadSheetProps) {
  const [busy, setBusy] = useState(false);

  return (
    <Sheet open={open} onOpenChange={(next) => (busy && !next ? undefined : onOpenChange(next))}>
      <SheetContent
        showCloseButton={!busy}
        className="w-full gap-0 data-[side=right]:sm:max-w-lg"
        onInteractOutside={(event) => (busy ? event.preventDefault() : undefined)}
      >
        <SheetHeader className="border-b">
          <SheetTitle>Новая сборка</SheetTitle>
          <SheetDescription>
            Сборка сохранится черновиком — опубликуйте её из истории, когда будете готовы. Максимальный размер файла —{" "}
            {formatBytes(maxBytes)}.
          </SheetDescription>
        </SheetHeader>
        <UploadForm
          initialFile={initialFile}
          releases={releases}
          maxBytes={maxBytes}
          onBusyChange={setBusy}
          onDone={() => onOpenChange(false)}
        />
      </SheetContent>
    </Sheet>
  );
}
