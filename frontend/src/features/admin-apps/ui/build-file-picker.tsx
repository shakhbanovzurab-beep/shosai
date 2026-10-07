"use client";

import { useRef } from "react";

import { cn } from "cn";
import { FileArchive, Upload, X } from "lucide-react";

import {
  Attachment,
  AttachmentAction,
  AttachmentActions,
  AttachmentContent,
  AttachmentDescription,
  AttachmentMedia,
  AttachmentTitle,
} from "@/components/ui/attachment";
import { Button } from "@/components/ui/button";

import { formatBytes } from "../domain/format";
import { ACCEPTED_EXTENSIONS } from "../domain/release-rules";
import { useFileHash } from "../model/use-file-hash";
import { useFileDrop } from "./file-drop";

type BuildFilePickerProps = {
  id: string;
  file: File | null;
  maxBytes: number;
  disabled: boolean;
  invalid: boolean;
  describedBy: string;
  onSelect: (file: File) => void;
  onClear: () => void;
};

const ACCEPT = ACCEPTED_EXTENSIONS.join(",");

/** Drop zone with a «Выбрать файл» button, then the chosen file with its checksum status. */
export function BuildFilePicker({
  id,
  file,
  maxBytes,
  disabled,
  invalid,
  describedBy,
  onSelect,
  onClear,
}: BuildFilePickerProps) {
  const input = useRef<HTMLInputElement>(null);
  const drop = useFileDrop(onSelect, !disabled);
  const hash = useFileHash(file);

  return (
    <div className="flex flex-col gap-2">
      <input
        ref={input}
        id={id}
        type="file"
        accept={ACCEPT}
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(event) => {
          const chosen = event.currentTarget.files?.[0];
          event.currentTarget.value = "";
          if (chosen) onSelect(chosen);
        }}
      />
      {file ? (
        <Attachment className="w-full" state={disabled ? "uploading" : "done"}>
          <AttachmentMedia>
            <FileArchive />
          </AttachmentMedia>
          <AttachmentContent>
            <AttachmentTitle title={file.name}>{file.name}</AttachmentTitle>
            <AttachmentDescription>
              {formatBytes(file.size)}
              {hash?.status === "hashing" ? " · вычисляем SHA-256…" : null}
              {hash?.status === "done" ? ` · SHA-256 ${hash.value.slice(0, 12)}…` : null}
              {hash?.status === "unavailable" ? " · SHA-256 посчитает сервер" : null}
            </AttachmentDescription>
          </AttachmentContent>
          <AttachmentActions>
            <AttachmentAction aria-label="Убрать файл" disabled={disabled} onClick={onClear}>
              <X />
            </AttachmentAction>
          </AttachmentActions>
        </Attachment>
      ) : (
        <div
          {...drop.handlers}
          aria-describedby={describedBy}
          className={cn(
            "flex flex-col items-center gap-3 rounded-xl border border-dashed px-4 py-8 text-center transition-colors",
            drop.isDragging && "border-primary bg-primary/5",
            invalid && "border-destructive",
          )}
        >
          <Upload className="size-5 text-muted-foreground" aria-hidden="true" />
          <div className="flex flex-col gap-1">
            <p className="font-medium text-sm">Перетащите файл сюда</p>
            <p className="text-muted-foreground text-xs">
              {ACCEPTED_EXTENSIONS.join(", ")} · до {formatBytes(maxBytes)}
            </p>
          </div>
          <Button type="button" variant="outline" size="sm" disabled={disabled} onClick={() => input.current?.click()}>
            Выбрать файл
          </Button>
        </div>
      )}
    </div>
  );
}
