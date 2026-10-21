"use client";

import { useId } from "react";

import { cn } from "cn";
import { useFormatter, useLocale, useTranslations } from "use-intl";

import { formatBytes } from "@/i18n/format-units";

import { ATTACHMENT_UPLOAD_MAX, ATTACHMENTS_MAX, type TaskDetail } from "../../domain/tasks-contract";
import { type AttachmentRow, attachCopies, attachFiles, useAttachmentRows } from "../../model/attachment-uploads";
import { useBoardStore } from "../../model/board-hooks";
import { AttachButtons } from "./attach-buttons";
import { AttachmentItem } from "./attachment-item";
import { AttachmentPending } from "./attachment-pending";
import { useFileDrop } from "./file-drop";

type Status = "attachments.drop" | "attachments.full" | "attachments.empty";

/** Что сказать под разделом: файлы над ним, предел, пустой раздел — или ничего. */
function statusKey({ over, full, empty }: { over: boolean; full: boolean; empty: boolean }): Status | null {
  if (over) return "attachments.drop";
  if (full) return "attachments.full";
  return empty ? "attachments.empty" : null;
}

/** Готовые вложения и те, что в пути или не прошли. */
function AttachmentList({ detail, rows, editable }: { detail: TaskDetail; rows: AttachmentRow[]; editable: boolean }) {
  if (detail.attachments.length === 0 && rows.length === 0) return null;
  return (
    <ul className="flex flex-col gap-2">
      {detail.attachments.map((attachment) => (
        <li key={attachment.id}>
          <AttachmentItem
            taskId={detail.id}
            attachment={attachment}
            isCover={detail.cover?.attachment_id === attachment.id}
            editable={editable}
          />
        </li>
      ))}
      {rows.map((row) => (
        <li key={row.id}>
          <AttachmentPending taskId={detail.id} row={row} />
        </li>
      ))}
    </ul>
  );
}

/**
 * Вложения: «Приложить» с компьютера, «Из моих файлов» копией, или бросить файлы на раздел. Загрузки и отказы —
 * строками рядом с готовыми; картинка становится обложкой карточки из её меню.
 */
export function PanelAttachments({ detail, editable }: { detail: TaskDetail; editable: boolean }) {
  const t = useTranslations("kanbanPanel");
  const format = useFormatter();
  const locale = useLocale();
  const store = useBoardStore();
  const rows = useAttachmentRows(detail.id);
  const headingId = useId();
  const full = detail.attachments.length + rows.length >= ATTACHMENTS_MAX;
  const canAttach = editable && !full;
  const workspaceId = detail.space?.workspace_id ?? null;
  const attach = (files: File[]) => (files.length > 0 ? attachFiles(detail.id, files, workspaceId, store) : undefined);
  const drop = useFileDrop(canAttach, attach);
  const key = statusKey({ over: drop.over, full, empty: detail.attachments.length === 0 && rows.length === 0 });

  if (!editable && detail.attachments.length === 0) return null;
  return (
    <section
      aria-labelledby={headingId}
      className={cn(
        "relative flex flex-col gap-2 rounded-lg",
        drop.over && "outline-dashed outline-2 outline-ring outline-offset-4",
      )}
      {...drop.dropProps}
    >
      <div className="flex flex-wrap items-center gap-2">
        <h3 id={headingId} className="me-auto flex items-center gap-2 font-medium text-sm">
          {t("attachments.label")}
          {detail.attachments.length > 0 ? (
            <span className="text-muted-foreground tabular-nums">{format.number(detail.attachments.length)}</span>
          ) : null}
        </h3>
        {editable ? (
          <AttachButtons
            disabled={!canAttach}
            onFiles={attach}
            onCopies={(files) => attachCopies(detail.id, files, store)}
          />
        ) : null}
      </div>
      <AttachmentList detail={detail} rows={rows} editable={editable} />
      {editable ? (
        <div className="flex flex-col gap-0.5 text-muted-foreground text-xs">
          {key ? <p>{t(key, { max: ATTACHMENTS_MAX })}</p> : null}
          {full ? null : <p>{t("attachments.limit", { size: formatBytes(locale, ATTACHMENT_UPLOAD_MAX) })}</p>}
        </div>
      ) : null}
    </section>
  );
}
