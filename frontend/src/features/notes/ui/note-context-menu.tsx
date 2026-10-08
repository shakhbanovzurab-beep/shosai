"use client";

import type * as React from "react";

import { cn } from "cn";
import { Download, ExternalLink, FolderInput, FolderPlus, Link2, NotebookText, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useTranslations } from "use-intl";

import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuRadioGroup,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import {
  ContextMenuItem,
  ContextMenuRadioItem,
  ContextMenuSeparator,
  ContextMenuShortcut,
} from "@/components/ui/context-menu-items";
import { ContextMenuSub, ContextMenuSubContent, ContextMenuSubTrigger } from "@/components/ui/context-menu-sub";
import { copyText } from "@/lib/copy-text";
import { useRouter } from "@/lib/navigation";

import { EXPORT_FORMATS } from "../domain/transcript-export";
import type { MeetingNote, NoteFolder } from "../domain/types";
import { FOLDER_DOT_CLASSES } from "./folder-color-classes";
import { useTranscriptDownload } from "./use-transcript-download";

const NO_FOLDER = "none";

interface NoteContextMenuProps {
  readonly note: MeetingNote;
  readonly folders: NoteFolder[];
  readonly onMove: (noteId: string, folderId: string | null, folderName: string) => void;
  readonly onMoveToNewFolder: (noteId: string) => void;
  readonly onDelete: (noteId: string, title: string) => void;
  readonly children: React.ReactNode;
}

/** Right-click menu for a note card. */
export function NoteContextMenu({
  note,
  folders,
  onMove,
  onMoveToNewFolder,
  onDelete,
  children,
}: NoteContextMenuProps) {
  const t = useTranslations("notes");
  const common = useTranslations("common");
  const router = useRouter();
  const transcript = useTranscriptDownload();
  const href = `/app/notes/${note.id}`;

  const copyLink = async () => {
    try {
      await copyText(new URL(href, window.location.origin).toString());
      toast.success(common("feedback.linkCopied"));
    } catch {
      toast.error(common("feedback.linkCopyFailed"));
    }
  };

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>
        <div className="grid">{children}</div>
      </ContextMenuTrigger>
      <ContextMenuContent className="w-56">
        <ContextMenuItem onSelect={() => router.push(href)}>
          <NotebookText />
          {common("actions.open")}
        </ContextMenuItem>
        <ContextMenuItem onSelect={() => window.open(href, "_blank", "noopener,noreferrer")}>
          <ExternalLink className="rtl:-scale-x-100" />
          {t("menu.openInNewTab")}
        </ContextMenuItem>
        <ContextMenuSeparator />
        <ContextMenuSub>
          <ContextMenuSubTrigger>
            <FolderInput />
            {t("folders.moveTo")}
          </ContextMenuSubTrigger>
          <ContextMenuSubContent className="w-48">
            <ContextMenuRadioGroup
              value={note.folderId ?? NO_FOLDER}
              onValueChange={(value) => {
                const folder = folders.find((f) => f.id === value);
                onMove(note.id, folder ? folder.id : null, folder ? folder.name : "");
              }}
            >
              <ContextMenuRadioItem value={NO_FOLDER}>{t("folders.none")}</ContextMenuRadioItem>
              {folders.map((folder) => (
                <ContextMenuRadioItem key={folder.id} value={folder.id}>
                  <span className={cn("size-2 rounded-full", FOLDER_DOT_CLASSES[folder.color])} aria-hidden="true" />
                  <span dir="auto">{folder.name}</span>
                </ContextMenuRadioItem>
              ))}
            </ContextMenuRadioGroup>
            <ContextMenuSeparator />
            <ContextMenuItem onSelect={() => onMoveToNewFolder(note.id)}>
              <FolderPlus />
              {t("folders.newMenu")}
            </ContextMenuItem>
          </ContextMenuSubContent>
        </ContextMenuSub>
        <ContextMenuItem onSelect={copyLink}>
          <Link2 />
          {common("actions.copyLink")}
        </ContextMenuItem>
        <ContextMenuSub>
          <ContextMenuSubTrigger>
            <Download />
            {t("menu.exportTranscript")}
          </ContextMenuSubTrigger>
          <ContextMenuSubContent className="w-52">
            {EXPORT_FORMATS.map((format) => (
              <ContextMenuItem key={format} onSelect={() => transcript.download(note, format)}>
                {transcript.formatName(format)}
                {/* A file extension reads left to right in every language. */}
                <ContextMenuShortcut dir="ltr">.{format}</ContextMenuShortcut>
              </ContextMenuItem>
            ))}
          </ContextMenuSubContent>
        </ContextMenuSub>
        <ContextMenuSeparator />
        <ContextMenuItem variant="destructive" onSelect={() => onDelete(note.id, note.title)}>
          <Trash2 />
          {common("actions.delete")}
        </ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  );
}
