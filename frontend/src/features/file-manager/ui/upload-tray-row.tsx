"use client";

import type { ReactNode } from "react";

import { cn } from "cn";
import { CircleCheck, File, RotateCw, X } from "lucide-react";
import { useLocale, useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Item, ItemActions, ItemContent, ItemDescription, ItemMedia, ItemTitle } from "@/components/ui/item";
import { Progress } from "@/components/ui/progress";
import { formatDuration } from "@/i18n/format-units";

import { MAX_FILES_PER_UPLOAD, MAX_UPLOAD_BYTES } from "../domain/contract";
import { extensionOf, isFinished, type UploadRow } from "../domain/upload-queue";
import { describeError } from "../model/problem-words";
import { retryUpload } from "../model/upload-actions";
import { uploadQueue } from "../model/upload-queue";
import { type FileActionWords, useFileActionWords } from "../model/words";

type Words = FileActionWords & { tray: ReturnType<typeof useTranslations<"fileManager">>; locale: string };

function refusalText(row: UploadRow, { tray, bytes }: Words): ReactNode {
  switch (row.refusal) {
    case "empty":
      return tray("upload.refused.empty");
    case "tooLarge":
      return tray("upload.refused.tooLarge", { size: bytes(MAX_UPLOAD_BYTES) });
    case "tooMany":
      return tray("upload.refused.tooMany", { max: MAX_FILES_PER_UPLOAD });
    default:
      return tray("upload.refused.unreadable");
  }
}

function sendingText(row: UploadRow, { tray, bytes, locale }: Words): ReactNode {
  const amounts = { sent: bytes(row.sent), size: bytes(row.size) };
  if (row.msLeft === null) return tray("upload.progress", amounts);
  // Секунды целые: десятые доли у оставшегося времени — шум.
  const time = formatDuration(locale, Math.ceil(row.msLeft / 1_000) * 1_000);
  return tray("upload.progressLeft", { ...amounts, time });
}

/** Подпись под именем: где файл сейчас, или почему он не загрузился. */
function statusText(row: UploadRow, words: Words): ReactNode {
  const { tray } = words;
  if (row.status === "waiting") return tray("upload.waiting");
  if (row.status === "sending") return sendingText(row, words);
  if (row.status === "saving") return tray("upload.finishing");
  if (row.status === "done") return row.leo ? tray("upload.doneLeo") : tray("upload.done");
  if (row.status === "failed") return describeError(row.error, words);
  return refusalText(row, words);
}

/** Один файл панели загрузок: тип, имя, где он сейчас, прогресс и то, что с ним можно сделать. */
export function UploadTrayRow({ row }: { row: UploadRow }) {
  const tray = useTranslations("fileManager");
  const common = useTranslations("common");
  const locale = useLocale();
  const words = useFileActionWords();
  const nameId = `upload-${row.id}`;
  const extension = extensionOf(row.name);
  const active = row.status === "waiting" || row.status === "sending";
  const problem = row.status === "failed" || row.status === "refused";

  return (
    <Item role="listitem" size="sm" className="flex-nowrap">
      {/* Ширина колонки постоянная, чтобы имена стояли ровно при «PDF» и «XLSX». */}
      <ItemMedia variant="icon" aria-hidden="true" className="w-12">
        {extension ? <Badge variant="secondary">{extension.slice(0, 4)}</Badge> : <File />}
      </ItemMedia>
      <ItemContent className="min-w-0">
        <ItemTitle className="max-w-full font-normal">
          <span id={nameId} className="truncate" dir="auto">
            {row.name}
          </span>
          {row.status === "done" ? (
            <CircleCheck className="size-4 shrink-0 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
          ) : null}
        </ItemTitle>
        <ItemDescription className={cn("line-clamp-none text-xs tabular-nums", problem && "text-destructive")}>
          {statusText(row, { ...words, tray, locale })}
        </ItemDescription>
        {row.status === "sending" ? (
          <Progress value={row.size > 0 ? (row.sent / row.size) * 100 : 0} aria-labelledby={nameId} />
        ) : null}
      </ItemContent>
      <ItemActions>
        {row.status === "failed" ? (
          <Button variant="ghost" size="sm" aria-describedby={nameId} onClick={() => void retryUpload(row.id, words)}>
            <RotateCw data-icon="inline-start" />
            {common("actions.retry")}
          </Button>
        ) : null}
        {active || isFinished(row) ? (
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={active ? tray("upload.cancel", { name: row.name }) : tray("upload.remove", { name: row.name })}
            onClick={() => uploadQueue.remove(row.id)}
          >
            <X />
          </Button>
        ) : null}
      </ItemActions>
    </Item>
  );
}
