"use client";

import * as React from "react";

import { useRouter } from "next/navigation";

import { Upload } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

import { formatBytes } from "@/i18n/format-units";

import { deriveLibrary } from "../domain/derive-library";
import { buildNotesHref, type NotesView } from "../domain/notes-href";
import { MAX_RECORDING_BYTES } from "../domain/recordings";
import type { MeetingNote, NoteGroup, PendingRecording } from "../domain/types";
import { folderActions, useNoteFolders } from "../model/folders-store";
import { useNoteEdits } from "../model/use-note-edits";
import { usePageDrop } from "../model/use-page-drop";
import { NoteContextMenu } from "./note-context-menu";
import { DraggableNote, NotesDndProvider } from "./notes-dnd";
import { NotesToolbar } from "./notes-toolbar";
import { EmptyFolder, GridView, ListView, TimelineView } from "./notes-views";

interface NotesLibraryProps {
  readonly groups: NoteGroup[];
  readonly activeFolderId: string | undefined;
  readonly view: NotesView;
}

let recordingCounter = 0;

export function NotesLibrary({ groups, activeFolderId: requestedFolderId, view }: NotesLibraryProps) {
  const t = useTranslations("notes");
  const locale = useLocale();
  const router = useRouter();
  const folders = useNoteFolders();
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const [recordings, setRecordings] = React.useState<PendingRecording[]>([]);
  const edits = useNoteEdits(groups);

  const { foldersById, activeFolderId, allNotes, countByFolder, featured, visibleGroups } = deriveLibrary(
    edits.groups,
    folders,
    requestedFolderId,
    view,
  );
  const folderOf = (note: MeetingNote) => (note.folderId ? foldersById.get(note.folderId) : undefined);

  const createFolder = () => {
    const folder = folderActions.create(t("folders.defaultName"));
    setEditingId(folder.id);
    return folder;
  };

  const moveToNewFolder = (noteId: string) => {
    const folder = createFolder();
    edits.moveNote(noteId, folder.id, folder.name);
  };

  const renameFolder = (id: string, name: string) => {
    folderActions.rename(id, name);
    setEditingId(null);
  };

  const deleteFolder = (id: string) => {
    folderActions.remove(id);
    if (id === activeFolderId) router.push(buildNotesHref({ view }), { scroll: false });
  };

  const addRecordings = (files: File[]) => {
    const added = files.map((file) => {
      recordingCounter += 1;
      return { id: `recording-${recordingCounter}`, name: file.name, size: file.size };
    });
    setRecordings((current) => [...added, ...current]);
  };

  const drop = usePageDrop(addRecordings);

  // Every meeting, in every view, gets the same right-click menu.
  const withMenu = (note: MeetingNote, content: React.ReactNode) => (
    <NoteContextMenu
      key={note.id}
      note={note}
      folders={folders}
      onMove={edits.moveNote}
      onMoveToNewFolder={moveToNewFolder}
      onDelete={edits.deleteNote}
    >
      <DraggableNote noteId={note.id}>{content}</DraggableNote>
    </NoteContextMenu>
  );

  const notesById = new Map(allNotes.map((note) => [note.id, note]));
  const dropOnFolder = (noteId: string, folderId: string | null) => {
    if (notesById.get(noteId)?.folderId === (folderId ?? undefined)) return;
    edits.moveNote(noteId, folderId, folderId ? (foldersById.get(folderId)?.name ?? "") : "");
  };

  const viewProps = {
    groups: visibleGroups,
    recordings,
    folderOf,
    withMenu,
    onRemoveRecording: (id: string) => setRecordings((current) => current.filter((r) => r.id !== id)),
  };
  const isEmpty = !featured && visibleGroups.length === 0 && recordings.length === 0;

  return (
    <NotesDndProvider titleOf={(id) => notesById.get(id)?.title} onDropOnFolder={dropOnFolder}>
      <div className="flex min-h-[calc(100dvh-var(--dashboard-header-height)-3rem)] flex-col gap-8" {...drop.handlers}>
        <h1 className="sr-only">{t("meta.title")}</h1>
        <NotesToolbar
          folders={folders}
          activeFolderId={activeFolderId}
          view={view}
          totalCount={allNotes.length}
          countByFolder={countByFolder}
          editingId={editingId}
          onCreate={() => {
            createFolder();
          }}
          onStartRename={setEditingId}
          onRename={renameFolder}
          onCancelRename={() => setEditingId(null)}
          onDelete={deleteFolder}
          onUpload={addRecordings}
        />

        {view === "timeline" ? <TimelineView {...viewProps} /> : null}
        {view === "grid" ? <GridView featured={featured} {...viewProps} /> : null}
        {view === "list" ? <ListView {...viewProps} /> : null}
        {isEmpty ? <EmptyFolder /> : null}

        {drop.isDragging ? (
          <div className="pointer-events-none fixed inset-3 z-40 flex flex-col items-center justify-center gap-3 rounded-3xl border-2 border-primary border-dashed bg-background/85 backdrop-blur-sm">
            <Upload className="size-8" aria-hidden="true" />
            <p className="font-medium text-lg">{t("upload.dropTitle")}</p>
            <p className="text-muted-foreground text-sm">
              {t("upload.dropHint", { size: formatBytes(locale, MAX_RECORDING_BYTES) })}
            </p>
          </div>
        ) : null}
      </div>
    </NotesDndProvider>
  );
}
