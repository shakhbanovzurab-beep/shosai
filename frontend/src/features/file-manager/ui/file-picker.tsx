"use client";

import { useState } from "react";

import { Search } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { LoadError } from "@/components/feedback";
import { Checkbox } from "@/components/ui/checkbox";
import { InputGroup, InputGroupAddon, InputGroupInput } from "@/components/ui/input-group";
import { Skeleton } from "@/components/ui/skeleton";
import { useFileSelection } from "@/features/workspace";
import { formatBytes } from "@/i18n/format-units";

import type { FileItem } from "../domain/contract";
import { filesResource, useFiles } from "../model/files-resource";
import { fileIcons } from "./file-icons";
import { useLeoBlocker } from "./leo-blocker";

type FilePickerProps = {
  isSelected: (fileId: string) => boolean;
  onToggle: (file: FileItem) => void;
  /** Why a file can't be picked here, in the interface language, shown under its name; null when it can. */
  unavailable?: (file: FileItem) => string | null;
  label: string;
};

/** The account's files with a search, to tick some for an action that lives elsewhere. */
export function FilePicker({ isSelected, onToggle, unavailable, label }: FilePickerProps) {
  const t = useTranslations("fileManager");
  const locale = useLocale();
  const files = useFiles();
  const [q, setQ] = useState("");
  if (files.status === "error")
    return <LoadError title={t("loadFailed")} message={files.message} onRetry={() => void filesResource.refresh()} />;
  if (files.status === "loading") return <Skeleton className="h-56 rounded-lg" />;
  const { folders } = files.data;
  const words = q.trim().toLowerCase();
  const shown = files.data.files.filter((f) => !words || f.name.toLowerCase().includes(words));

  return (
    <div className="flex min-h-0 flex-col gap-2">
      <InputGroup>
        <InputGroupAddon>
          <Search aria-hidden="true" />
        </InputGroupAddon>
        <InputGroupInput
          type="search"
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder={t("picker.search")}
          aria-label={t("picker.search")}
        />
      </InputGroup>
      <ul className="max-h-64 min-h-0 divide-y overflow-y-auto rounded-lg border" aria-label={label}>
        {shown.length === 0 ? (
          <li className="px-3 py-6 text-center text-muted-foreground text-sm">
            {files.data.files.length ? t("picker.noMatch") : t("picker.noFiles")}
          </li>
        ) : null}
        {shown.map((file) => {
          const reason = unavailable?.(file) ?? null;
          const Icon = fileIcons[file.kind];
          const folder = folders.find((f) => f.id === file.folder_id);
          const id = `pick-${file.id}`;
          return (
            <li key={file.id} className="flex items-center gap-3 px-3 py-2 has-[:disabled]:opacity-60">
              <Checkbox
                id={id}
                checked={isSelected(file.id)}
                disabled={reason !== null}
                onCheckedChange={() => onToggle(file)}
              />
              <Icon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
              <label htmlFor={id} className="flex min-w-0 flex-1 cursor-pointer flex-col">
                <span className="truncate text-sm" dir="auto">
                  {file.name}
                </span>
                <span className="truncate text-muted-foreground text-xs">
                  {reason ?? (
                    <>
                      <bdi>{folder?.name ?? t("myFiles")}</bdi> · {formatBytes(locale, file.size_bytes)}
                    </>
                  )}
                </span>
              </label>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** The picker inside a workspace's "Share from my files" dialog: only files Leo can read, not shared there yet. */
export function WorkspaceFilePicker() {
  const t = useTranslations("fileManager");
  const blocker = useLeoBlocker();
  const selection = useFileSelection();
  if (!selection) return null;
  return (
    <FilePicker
      label={t("picker.yourFiles")}
      isSelected={selection.isSelected}
      onToggle={(file) => selection.toggle(file)}
      unavailable={(file) => blocker(file) ?? (selection.sharedHere.has(file.id) ? t("picker.alreadyShared") : null)}
    />
  );
}
