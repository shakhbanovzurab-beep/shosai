"use client";

import { AudioLines, CircleAlert } from "lucide-react";
import { useTranslations } from "use-intl";

import { ShosaiMark } from "@/components/shosai-mark";

import type { MeetingPage } from "../domain/meeting-page";
import { runFailureOf } from "../domain/problems";
import { useRun } from "../model/write-up";

const NOTICE =
  "flex items-start gap-2 rounded-lg border bg-muted/40 px-3 py-2 text-sm [&_svg]:mt-0.5 [&_svg]:size-4 [&_svg]:shrink-0";

/** Тихие пометки под заголовком: встреча идёт, записи пишутся, не вышли или обновились с голосами записи. */
export function NoteNotices({ note }: { readonly note: MeetingPage }) {
  const t = useTranslations("notesNote");
  if (note.status === "active")
    return (
      <p className={NOTICE} role="status">
        <AudioLines aria-hidden="true" className="text-amber-600 dark:text-amber-400" />
        {t("notices.live")}
      </p>
    );
  if (note.notes === "processing")
    return (
      <p className={NOTICE} role="status">
        <ShosaiMark className="text-amber-600 dark:text-amber-400" />
        {t("notices.writing")}
      </p>
    );
  // Причина и голоса записи — у последнего прогона; его видит только владелец встречи.
  if (note.runId && note.owned) return <RunNotice runId={note.runId} failed={note.notes === "failed"} />;
  if (note.notes !== "failed") return null;
  return (
    <p className={NOTICE} role="status">
      <CircleAlert aria-hidden="true" className="text-destructive" />
      {t("notices.failed.other")}
    </p>
  );
}

function RunNotice({ runId, failed }: { readonly runId: string; readonly failed: boolean }) {
  const t = useTranslations("notesNote");
  const run = useRun(runId);
  if (run.status !== "ready") return null;
  if (failed)
    return (
      <p className={NOTICE} role="status">
        <CircleAlert aria-hidden="true" className="text-destructive" />
        {t(`notices.failed.${runFailureOf(run.data.error_code)}`)}
      </p>
    );
  const done = run.data.state === "succeeded" || run.data.state === "partially_completed";
  if (run.data.source !== "recording" || !done) return null;
  return (
    <p className={NOTICE}>
      <AudioLines aria-hidden="true" className="text-muted-foreground" />
      {t("notices.speakers")}
    </p>
  );
}
