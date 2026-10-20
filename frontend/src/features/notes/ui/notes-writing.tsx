"use client";

import { useTranslations } from "use-intl";

import { Skeleton } from "@/components/ui/skeleton";

/** Место записи Leo, пока он её пишет: три серых раздела и статус для читалок экрана. */
export function NotesWriting() {
  const t = useTranslations("notesNote");
  return (
    <div className="flex flex-col gap-6" aria-busy="true">
      <span className="sr-only" role="status">
        {t("enhanced.writing")}
      </span>
      {[0, 1, 2].map((row) => (
        <div key={row} className="flex flex-col gap-2.5">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-4/5" />
        </div>
      ))}
    </div>
  );
}
