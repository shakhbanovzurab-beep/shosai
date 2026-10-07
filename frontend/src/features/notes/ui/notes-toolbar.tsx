"use client";

import * as React from "react";

import { useRouter } from "next/navigation";

import { GitCommitVertical, LayoutGrid, List, Upload } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import { buildNotesHref, type NotesView } from "../domain/notes-href";
import { RECORDING_ACCEPT } from "../domain/recordings";
import { filterRecordings } from "../model/recordings";
import { FolderPills, type FolderPillsProps } from "./folder-pills";

const VIEW_OPTIONS = [
  { value: "timeline", icon: GitCommitVertical },
  { value: "grid", icon: LayoutGrid },
  { value: "list", icon: List },
] as const satisfies readonly { value: NotesView; icon: typeof List }[];

interface NotesToolbarProps extends FolderPillsProps {
  readonly onUpload: (files: File[]) => void;
}

export function NotesToolbar({ onUpload, ...folderProps }: NotesToolbarProps) {
  const t = useTranslations("notes");
  const locale = useLocale();
  const router = useRouter();
  const inputRef = React.useRef<HTMLInputElement>(null);
  const { view, activeFolderId } = folderProps;

  return (
    <div className="flex items-center gap-4">
      <FolderPills {...folderProps} />
      <div className="flex shrink-0 items-center gap-2">
        <ToggleGroup
          type="single"
          variant="outline"
          spacing={0}
          value={view}
          aria-label={t("views.label")}
          onValueChange={(next) => {
            const option = VIEW_OPTIONS.find((o) => o.value === next);
            if (option)
              router.replace(buildNotesHref({ folder: activeFolderId, view: option.value }), { scroll: false });
          }}
        >
          {/* On small screens the name stays for screen readers, as the item's accessible name. */}
          {VIEW_OPTIONS.map(({ value, icon: Icon }) => (
            <ToggleGroupItem key={value} value={value} className="gap-1.5 px-3">
              <Icon />
              <span className="max-sm:sr-only">{t(`views.${value}`)}</span>
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <input
          ref={inputRef}
          type="file"
          accept={RECORDING_ACCEPT}
          multiple
          className="sr-only"
          tabIndex={-1}
          aria-hidden="true"
          onChange={(event) => {
            const accepted = event.target.files ? filterRecordings(event.target.files, t, locale) : [];
            if (accepted.length > 0) onUpload(accepted);
            event.target.value = "";
          }}
        />
        <Button onClick={() => inputRef.current?.click()} title={t("upload.hint")}>
          <Upload data-icon="inline-start" />
          <span className="max-md:sr-only">{t("upload.button")}</span>
        </Button>
      </div>
    </div>
  );
}
