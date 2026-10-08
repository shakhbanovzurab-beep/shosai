"use client";

import { useRef } from "react";

import { FileText, Paperclip, X } from "lucide-react";
import { useLocale, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { formatBytes } from "@/i18n/format-units";

/** The paperclip button with its hidden file input. */
export function AttachButton({ onAdd, disabled }: { onAdd: (files: File[]) => void; disabled?: boolean }) {
  const t = useTranslations("pagesSupport");
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        aria-label={t("attach.button")}
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
      >
        <Paperclip />
      </Button>
      <input
        ref={inputRef}
        type="file"
        multiple
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(event) => {
          onAdd([...(event.currentTarget.files ?? [])]);
          event.currentTarget.value = "";
        }}
      />
    </>
  );
}

/** Chips for files waiting to be sent, each removable. */
export function PendingFiles({ files, onRemove }: { files: File[]; onRemove: (index: number) => void }) {
  const t = useTranslations("pagesSupport");
  const locale = useLocale();
  if (files.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-2" aria-label={t("attach.list")}>
      {files.map((file, index) => (
        <li
          key={`${file.name}-${file.size}-${file.lastModified}`}
          className="flex max-w-56 items-center gap-1.5 rounded-md border bg-muted/50 py-1 ps-2 pe-1 text-xs"
        >
          <FileText className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
          <span dir="auto" className="truncate">
            {file.name}
          </span>
          <span className="shrink-0 text-muted-foreground">{formatBytes(locale, file.size)}</span>
          <Button
            variant="ghost"
            size="icon-xs"
            aria-label={t("attach.remove", { name: file.name })}
            onClick={() => onRemove(index)}
          >
            <X />
          </Button>
        </li>
      ))}
    </ul>
  );
}
