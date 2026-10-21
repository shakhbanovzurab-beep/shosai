"use client";

import { CircleAlert, X } from "lucide-react";
import { useLocale, useTranslations } from "use-intl";

import { Attachment, AttachmentContent, AttachmentMedia } from "@/components/ui/attachment";
import {
  AttachmentAction,
  AttachmentActions,
  AttachmentDescription,
  AttachmentTitle,
} from "@/components/ui/attachment-parts";
import { Progress } from "@/components/ui/progress";
import { Spinner } from "@/components/ui/spinner";
import { formatBytes } from "@/i18n/format-units";

import { type AttachmentRow, cancelUpload, dismissRow } from "../../model/attachment-uploads";
import { describeProblem } from "../../model/words";

/** Вложение в пути: ход загрузки с отменой, копия из File Manager — или отказ с причиной, пока его не уберут. */
export function AttachmentPending({ taskId, row }: { taskId: string; row: AttachmentRow }) {
  const t = useTranslations("kanbanPanel");
  const ta = useTranslations("kanbanApi");
  const locale = useLocale();
  if (row.failure !== null) {
    const reason = typeof row.failure === "string" ? ta(row.failure) : describeProblem(row.failure.error, ta);
    return (
      <Attachment state="error" className="w-full" role="alert">
        <AttachmentMedia>
          <CircleAlert />
        </AttachmentMedia>
        <AttachmentContent>
          <AttachmentTitle>
            <bdi>{row.name}</bdi>
          </AttachmentTitle>
          <AttachmentDescription className="whitespace-normal">{reason}</AttachmentDescription>
        </AttachmentContent>
        <AttachmentActions>
          <AttachmentAction
            aria-label={t("attachments.dismiss", { name: row.name })}
            onClick={() => dismissRow(taskId, row.id)}
          >
            <X />
          </AttachmentAction>
        </AttachmentActions>
      </Attachment>
    );
  }
  // Копия не передаёт байтов: её ход не показывается, только что она идёт.
  const copying = row.kind === "copy";
  const progress = t("attachments.uploading", {
    sent: formatBytes(locale, row.sent),
    total: formatBytes(locale, row.size),
  });
  return (
    <Attachment state="uploading" className="w-full" aria-busy="true">
      <AttachmentMedia>
        <Spinner />
      </AttachmentMedia>
      <AttachmentContent className="flex flex-col gap-1">
        <AttachmentTitle>
          <bdi>{row.name}</bdi>
        </AttachmentTitle>
        <AttachmentDescription>{copying ? t("attachments.copying") : progress}</AttachmentDescription>
        {copying ? null : (
          <Progress value={row.size > 0 ? (row.sent / row.size) * 100 : 0} aria-label={progress} className="h-1" />
        )}
      </AttachmentContent>
      {copying ? null : (
        <AttachmentActions>
          <AttachmentAction
            aria-label={t("attachments.cancel", { name: row.name })}
            onClick={() => cancelUpload(row.id)}
          >
            <X />
          </AttachmentAction>
        </AttachmentActions>
      )}
    </Attachment>
  );
}
