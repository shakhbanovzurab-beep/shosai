"use client";

import { useRef, useState } from "react";

import { cn } from "cn";
import { CloudUpload, FolderSearch } from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { isLeoReadable, LEO_EXTENSIONS, LEO_MAX_FILE_BYTES } from "@/features/file-manager/domain/contract";
import { screenFiles } from "@/features/file-manager/domain/upload-queue";
import { refuseFiles, uploadFiles } from "@/features/file-manager/model/upload-actions";
import { useFileActionWords } from "@/features/file-manager/model/words";
import { formatBytes } from "@/i18n/format-units";

/**
 * Drop or pick files for Leo: they go to My files in File Manager (the one place files live) and are
 * marked "Use with Leo" at once. Or choose files already there. Как идут файлы, показывает панель загрузок
 * под этой зоной; файл, который Leo не прочтёт, становится в ней строкой с причиной.
 */
export function UploadDropzone({ onChoose }: { onChoose: () => void }) {
  const t = useTranslations("knowledgeBase");
  const format = useFormatter();
  const locale = useLocale();
  const words = useFileActionWords();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isOver, setIsOver] = useState(false);

  function upload(files: File[]) {
    const target = { folderId: null, leo: true };
    const { accepted, refused } = screenFiles(files, (file) => isLeoReadable(file.name, file.size));
    refuseFiles(refused, target);
    if (accepted.length > 0) void uploadFiles(accepted, target, words);
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
        upload([...event.dataTransfer.files]);
      }}
      className={cn(
        "flex flex-col items-center gap-3 rounded-xl border border-dashed bg-muted/30 px-6 py-8 text-center transition-colors",
        isOver && "border-primary bg-primary/5",
      )}
    >
      <div className="grid size-11 place-items-center rounded-full border bg-background">
        <CloudUpload className="size-5 text-muted-foreground" />
      </div>
      <div className="flex flex-col gap-1">
        <p className="font-medium">{t("dropzone.title")}</p>
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
        <Button variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
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
          upload([...(event.currentTarget.files ?? [])]);
          event.currentTarget.value = "";
        }}
      />
    </section>
  );
}
