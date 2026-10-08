"use client";

import { useRef, useState } from "react";

import { cn } from "cn";
import { CloudUpload, FolderSearch } from "lucide-react";
import { toast } from "sonner";
import { useFormatter, useLocale, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { LEO_EXTENSIONS, LEO_MAX_FILE_BYTES, MAX_FILES_PER_UPLOAD } from "@/features/file-manager/domain/contract";
import { uploadFiles } from "@/features/file-manager/model/file-actions";
import { useFileActionWords } from "@/features/file-manager/model/words";
import { formatBytes } from "@/i18n/format-units";

import { triage } from "../model/leo-files";

/**
 * Drop or pick files for Leo: they go to My files in File Manager (the one place files live) and are
 * marked "Use with Leo" at once. Or choose files already there.
 */
export function UploadDropzone({ onChoose }: { onChoose: () => void }) {
  const t = useTranslations("knowledgeBase");
  const format = useFormatter();
  const locale = useLocale();
  const words = useFileActionWords();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isOver, setIsOver] = useState(false);
  const [uploading, setUploading] = useState(0);

  async function upload(files: File[]) {
    const { accepted, rejected } = triage(files);
    const reasons = rejected.map(({ name, reason }) =>
      reason === "unreadable"
        ? t("dropzone.unreadable", { name })
        : t("dropzone.tooMany", { name, max: MAX_FILES_PER_UPLOAD }),
    );
    if (rejected.length)
      toast.error(t("dropzone.skipped", { count: rejected.length }), { description: reasons.join("\n") });
    if (accepted.length === 0) return;
    setUploading(accepted.length);
    await uploadFiles(accepted, { folderId: null, leo: true }, words);
    setUploading(0);
  }

  return (
    <section
      aria-label={t("dropzone.label")}
      onDragOver={(event) => {
        event.preventDefault();
        setIsOver(true);
      }}
      onDragLeave={() => setIsOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setIsOver(false);
        void upload([...event.dataTransfer.files]);
      }}
      className={cn(
        "flex flex-col items-center gap-3 rounded-xl border border-dashed bg-muted/30 px-6 py-8 text-center transition-colors",
        isOver && "border-primary bg-primary/5",
      )}
    >
      <div className="grid size-11 place-items-center rounded-full border bg-background">
        {uploading ? <Spinner /> : <CloudUpload className="size-5 text-muted-foreground" />}
      </div>
      <div className="flex flex-col gap-1">
        <p className="font-medium">{uploading ? t("dropzone.uploading", { count: uploading }) : t("dropzone.title")}</p>
        <p className="text-muted-foreground text-sm">
          {t("dropzone.description", {
            types: format.list(
              LEO_EXTENSIONS.map((ext) => ext.slice(1).toUpperCase()),
              { type: "unit", style: "short" },
            ),
            size: formatBytes(locale, LEO_MAX_FILE_BYTES),
          })}
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        <Button size="sm" onClick={onChoose}>
          <FolderSearch data-icon="inline-start" />
          {t("dropzone.choose")}
        </Button>
        <Button variant="outline" size="sm" disabled={uploading > 0} onClick={() => inputRef.current?.click()}>
          {t("dropzone.upload")}
        </Button>
      </div>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={LEO_EXTENSIONS.join(",")}
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(event) => {
          void upload([...(event.currentTarget.files ?? [])]);
          event.currentTarget.value = "";
        }}
      />
    </section>
  );
}
