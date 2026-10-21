"use client";

import { useRef } from "react";

import { Paperclip } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import type { FileItem } from "@/features/file-manager/domain/contract";

import { FromFilesDialog } from "./from-files-dialog";

/** «Приложить» открывает выбор файлов компьютера, «Из моих файлов» — файлы File Manager. */
export function AttachButtons({
  disabled,
  onFiles,
  onCopies,
}: {
  disabled: boolean;
  onFiles: (files: File[]) => void;
  onCopies: (files: FileItem[]) => void;
}) {
  const t = useTranslations("kanbanPanel");
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={input}
        type="file"
        multiple
        hidden
        onChange={(event) => {
          onFiles([...(event.currentTarget.files ?? [])]);
          event.currentTarget.value = "";
        }}
      />
      <Button variant="outline" size="sm" disabled={disabled} onClick={() => input.current?.click()}>
        <Paperclip data-icon="inline-start" />
        {t("attachments.attach")}
      </Button>
      <FromFilesDialog disabled={disabled} onAttach={onCopies} />
    </>
  );
}
