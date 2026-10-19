"use client";

import { useFormatter, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Card, CardAction, CardHeader, CardTitle } from "@/components/ui/card";
import { ItemGroup } from "@/components/ui/item";

import { traySummary } from "../domain/upload-queue";
import { uploadQueue, useUploadRows, useUploadTrayPresence } from "../model/upload-queue";
import { UploadTrayRow } from "./upload-tray-row";

/**
 * Загрузки этой вкладки по строке на файл. Пока файлы идут — сколько их и сколько осталось; потом тихое
 * «загружено», которое уходит само, и отказы с причиной, которые ждут человека. Нет загрузок — нет панели.
 */
export function UploadTray() {
  useUploadTrayPresence();
  const t = useTranslations("fileManager");
  const format = useFormatter();
  const rows = useUploadRows();
  if (rows.length === 0) return null;

  const { active, done, failed, percent } = traySummary(rows);
  let headline = t("upload.uploaded", { count: done });
  if (failed > 0) headline = t("upload.notUploaded", { count: failed });
  if (active > 0) headline = t("upload.uploading", { count: active });

  return (
    <section aria-label={t("upload.label")}>
      <Card size="sm">
        <CardHeader className="border-b">
          <CardTitle role="status" className="self-center">
            {headline}
          </CardTitle>
          <CardAction>
            {active > 0 ? (
              <span aria-hidden="true" className="text-muted-foreground tabular-nums">
                {format.number(percent / 100, { style: "percent" })}
              </span>
            ) : (
              <Button variant="ghost" size="sm" onClick={uploadQueue.clearFinished}>
                {t("upload.clear")}
              </Button>
            )}
          </CardAction>
        </CardHeader>
        <ItemGroup className="max-h-80 overflow-y-auto">
          {rows.map((row) => (
            <UploadTrayRow key={row.id} row={row} />
          ))}
        </ItemGroup>
      </Card>
    </section>
  );
}
