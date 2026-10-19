"use client";

import { type ReactNode, useRef, useState } from "react";

import { cn } from "cn";
import { CloudUpload, Upload } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";

import { screenFiles } from "../domain/upload-queue";
import { refuseFiles, uploadFiles } from "../model/upload-actions";
import { useFileActionWords } from "../model/words";

/** Uploads into `folderId`; what can't go becomes a row of the panel with its reason. */
function useUpload(folderId: string | null) {
  const words = useFileActionWords();
  return (picked: File[]) => {
    const target = { folderId, leo: false };
    const { accepted, refused } = screenFiles(picked);
    refuseFiles(refused, target);
    if (accepted.length > 0) void uploadFiles(accepted, target, words);
  };
}

/** "Upload" into the folder being shown, or into My files. Панель загрузок показывает, как идут файлы. */
export function UploadButton({ folderId }: { folderId: string | null }) {
  const t = useTranslations("fileManager");
  const inputRef = useRef<HTMLInputElement>(null);
  const upload = useUpload(folderId);
  return (
    <>
      <Button size="sm" onClick={() => inputRef.current?.click()}>
        <Upload data-icon="inline-start" />
        {t("upload.button")}
      </Button>
      <input
        ref={inputRef}
        type="file"
        multiple
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(event) => {
          upload([...(event.currentTarget.files ?? [])]);
          event.currentTarget.value = "";
        }}
      />
    </>
  );
}

/** Accepts files dragged in from the computer anywhere over `children`, and uploads them here. */
export function FileDropZone({ folderId, children }: { folderId: string | null; children: ReactNode }) {
  const t = useTranslations("fileManager");
  const [over, setOver] = useState(false);
  const upload = useUpload(folderId);
  const fromComputer = (event: React.DragEvent) => event.dataTransfer.types.includes("Files");

  return (
    <section
      aria-label={t("section.label")}
      className={cn("relative flex flex-col gap-2 rounded-xl", over && "ring-2 ring-primary ring-offset-4")}
      onDragOver={(event) => {
        if (!fromComputer(event)) return;
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOver(false);
      }}
      onDrop={(event) => {
        if (!fromComputer(event)) return;
        event.preventDefault();
        setOver(false);
        upload([...event.dataTransfer.files]);
      }}
    >
      {children}
      {over ? (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-xl bg-background/80">
          <span className="flex items-center gap-2 font-medium text-sm">
            <CloudUpload className="size-5" aria-hidden="true" />
            {t("upload.dropHere")}
          </span>
        </div>
      ) : null}
    </section>
  );
}
