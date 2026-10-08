"use client";

import * as React from "react";

import { cn } from "cn";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { useTranslations } from "use-intl";

import { ContextMenu, ContextMenuContent, ContextMenuTrigger } from "@/components/ui/context-menu";
import { ContextMenuItem } from "@/components/ui/context-menu-items";
import { Link } from "@/lib/navigation";

import { buildNotesHref, type NotesView } from "../domain/notes-href";
import type { NoteFolder } from "../domain/types";
import { FOLDER_DOT_CLASSES } from "./folder-color-classes";
import { FolderNameInput } from "./folder-name-input";
import { useFolderDrop } from "./notes-dnd";
import { useHorizontalWheel } from "./use-horizontal-wheel";

const PILL_CLASSES =
  "inline-flex h-9 shrink-0 items-center gap-2 whitespace-nowrap rounded-full border px-3.5 text-sm outline-none transition-[color,background-color,box-shadow,scale] focus-visible:ring-3 focus-visible:ring-ring/50";
const ACTIVE_PILL = "border-primary bg-primary font-medium text-primary-foreground";
const IDLE_PILL = "border-border text-muted-foreground hover:bg-muted hover:text-foreground";
// While a meeting is dragged over a pill.
const DROP_TARGET_PILL = "scale-105 ring-2 ring-primary ring-offset-2 ring-offset-background";

function AllMeetingsPill({
  href,
  isActive,
  count,
}: {
  readonly href: string;
  readonly isActive: boolean;
  readonly count: number;
}) {
  const t = useTranslations("notes");
  const { ref, isDropTarget } = useFolderDrop(null);
  return (
    <Link
      ref={ref}
      href={href}
      scroll={false}
      aria-current={isActive ? "page" : undefined}
      className={cn(PILL_CLASSES, isActive ? ACTIVE_PILL : IDLE_PILL, isDropTarget && DROP_TARGET_PILL)}
    >
      {t("folders.all")}
      <span className="font-mono text-xs tabular-nums opacity-60">{count}</span>
    </Link>
  );
}

export interface FolderPillsProps {
  readonly folders: NoteFolder[];
  readonly activeFolderId: string | undefined;
  readonly view: NotesView;
  readonly totalCount: number;
  readonly countByFolder: Map<string, number>;
  readonly editingId: string | null;
  readonly onCreate: () => void;
  readonly onStartRename: (id: string) => void;
  readonly onRename: (id: string, name: string) => void;
  readonly onCancelRename: () => void;
  readonly onDelete: (id: string) => void;
}

/** Folder filter as a row of pills; right-click a folder to rename or delete it. */
export function FolderPills({
  folders,
  activeFolderId,
  view,
  totalCount,
  countByFolder,
  ...actions
}: FolderPillsProps) {
  const t = useTranslations("notes");
  const scrollerRef = React.useRef<HTMLDivElement>(null);
  useHorizontalWheel(scrollerRef);

  return (
    <nav aria-label={t("folders.label")} className="flex min-w-0 flex-1 items-center gap-1.5">
      {/* Pills scroll sideways inside their own row, so new folders never push the toolbar actions away. */}
      <div
        ref={scrollerRef}
        className="no-scrollbar scroll-fade-x flex min-w-0 items-center gap-1.5 overflow-x-auto overscroll-x-contain px-1 py-1.5"
      >
        <AllMeetingsPill href={buildNotesHref({ view })} isActive={!activeFolderId} count={totalCount} />
        {folders.map((folder) => (
          <FolderPill
            key={folder.id}
            folder={folder}
            href={buildNotesHref({ folder: folder.id, view })}
            isActive={folder.id === activeFolderId}
            isEditing={folder.id === actions.editingId}
            count={countByFolder.get(folder.id) ?? 0}
            {...actions}
          />
        ))}
      </div>
      <button
        type="button"
        aria-label={t("folders.new")}
        onClick={actions.onCreate}
        className="inline-flex size-9 shrink-0 items-center justify-center rounded-full border border-dashed text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-3 focus-visible:ring-ring/50"
      >
        <Plus className="size-4" />
      </button>
    </nav>
  );
}

interface FolderPillProps
  extends Omit<
    FolderPillsProps,
    "folders" | "activeFolderId" | "view" | "totalCount" | "countByFolder" | "editingId" | "onCreate"
  > {
  readonly folder: NoteFolder;
  readonly href: string;
  readonly isActive: boolean;
  readonly isEditing: boolean;
  readonly count: number;
}

function FolderPill({
  folder,
  href,
  isActive,
  isEditing,
  count,
  onStartRename,
  onRename,
  onCancelRename,
  onDelete,
}: FolderPillProps) {
  const common = useTranslations("common");
  const { ref, isDropTarget } = useFolderDrop(folder.id);
  const dot = (
    <span className={cn("size-2 shrink-0 rounded-full", FOLDER_DOT_CLASSES[folder.color])} aria-hidden="true" />
  );

  if (isEditing) {
    return (
      <span className={cn(PILL_CLASSES, "border-ring")}>
        {dot}
        <FolderNameInput
          initialName={folder.name}
          onSubmit={(name) => onRename(folder.id, name)}
          onCancel={onCancelRename}
        />
      </span>
    );
  }

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>
        <Link
          ref={ref}
          href={href}
          scroll={false}
          aria-current={isActive ? "page" : undefined}
          className={cn(PILL_CLASSES, isActive ? ACTIVE_PILL : IDLE_PILL, isDropTarget && DROP_TARGET_PILL)}
        >
          {dot}
          <span dir="auto">{folder.name}</span>
          <span className="font-mono text-xs tabular-nums opacity-60">{count}</span>
        </Link>
      </ContextMenuTrigger>
      <ContextMenuContent className="w-40">
        <ContextMenuItem onSelect={() => onStartRename(folder.id)}>
          <Pencil />
          {common("actions.rename")}
        </ContextMenuItem>
        <ContextMenuItem variant="destructive" onSelect={() => onDelete(folder.id)}>
          <Trash2 />
          {common("actions.delete")}
        </ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  );
}
