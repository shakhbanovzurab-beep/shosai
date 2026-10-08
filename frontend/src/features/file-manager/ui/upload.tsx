"use client";

import { type ReactNode, useRef, useState } from "react";

import { cn } from "cn";
import { CloudUpload, Upload } from "lucide-react";
import { toast } from "sonner";
import { useLocale, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { formatBytes } from "@/i18n/format-units";

import { MAX_FILES_PER_UPLOAD, MAX_UPLOAD_BYTES } from "../domain/contract";
import { uploadFiles } from "../model/file-actions";
import { useFileActionWords } from "../model/words";

/** Uploads into `folderId` after checking the limits; one at a time, so the button can show it's busy. */
function useUpload(folderId: string | null) {
  const t = useTranslations("fileManager");
  const locale = useLocale();
  const words = useFileActionWords();
  const [busy, setBusy] = useState(0);
  const upload = async (picked: File[]) => {
    const fits = picked.filter((f) => f.size <= MAX_UPLOAD_BYTES && f.size > 0).slice(0, MAX_FILES_PER_UPLOAD);
    const skipped = picked.length - fits.length;
    if (skipped)
      toast.error(t("upload.skipped", { count: skipped }), {
        description: t("upload.skippedDescription", {
          size: formatBytes(locale, MAX_UPLOAD_BYTES),
          max: MAX_FILES_PER_UPLOAD,
        }),
      });
    if (fits.length === 0) return;
    setBusy(fits.length);
    await uploadFiles(fits, { folderId, leo: false }, words);
    setBusy(0);
  };
  return { busy, upload };
}

/** "Upload" into the folder being shown, or into My files. */
export function UploadButton({ folderId }: { folderId: string | null }) {
  const t = useTranslations("fileManager");
  const inputRef = useRef<HTMLInputElement>(null);
  const { busy, upload } = useUpload(folderId);
  return (
    <>
      <Button size="sm" disabled={busy > 0} onClick={() => inputRef.current?.click()}>
        {busy ? <Spinner data-icon="inline-start" /> : <Upload data-icon="inline-start" />}
        {busy ? t("upload.uploading", { count: busy }) : t("upload.button")}
      </Button>
      <input
        ref={inputRef}
        type="file"
        multiple
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(event) => {
          void upload([...(event.currentTarget.files ?? [])]);
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
  const { upload } = useUpload(folderId);
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
        void upload([...event.dataTransfer.files]);
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
