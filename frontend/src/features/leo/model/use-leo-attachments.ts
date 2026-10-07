"use client";

import * as React from "react";

import { useLocale, useTranslations } from "next-intl";
import { toast } from "sonner";

import { formatBytes } from "@/i18n/format-units";

import { LEO_MAX_ATTACHMENT_BYTES, LEO_MAX_ATTACHMENTS } from "../domain/attachments";

export interface PendingFile {
  id: string;
  file: File;
}

let fileCounter = 0;

export function useLeoAttachments() {
  const t = useTranslations("leo");
  const locale = useLocale();
  const [files, setFiles] = React.useState<PendingFile[]>([]);

  const addFiles = (incoming: Iterable<File>) => {
    const accepted: PendingFile[] = [];
    for (const file of incoming) {
      if (file.size > LEO_MAX_ATTACHMENT_BYTES) {
        toast.error(t("attachments.tooLarge", { name: file.name }), {
          description: t("attachments.sizeLimit", { size: formatBytes(locale, LEO_MAX_ATTACHMENT_BYTES) }),
        });
        continue;
      }
      fileCounter += 1;
      accepted.push({ id: `file-${fileCounter}`, file });
    }

    const room = LEO_MAX_ATTACHMENTS - files.length;
    if (accepted.length > room) toast.error(t("attachments.tooMany", { max: LEO_MAX_ATTACHMENTS }));
    const added = accepted.slice(0, Math.max(room, 0));
    if (added.length > 0) setFiles((current) => [...current, ...added].slice(0, LEO_MAX_ATTACHMENTS));
  };

  const removeFile = (id: string) => setFiles((current) => current.filter((f) => f.id !== id));

  const clearFiles = () => setFiles([]);

  return { files, addFiles, removeFile, clearFiles };
}
