"use client";

import * as React from "react";

import { Upload } from "lucide-react";
import { useLocale, useTranslations } from "use-intl";

import { formatBytes } from "@/i18n/format-units";
import { useTimeZone } from "@/i18n/time-zone";
import { useRouter } from "@/lib/navigation";

import { deriveLibrary, hasFeaturedSlot } from "../domain/derive-library";
import type { LibraryCounts, MeetingCard } from "../domain/library";
import { buildNotesHref, type NotesView } from "../domain/notes-href";
import { MAX_RECORDING_BYTES } from "../domain/recordings";
import type { NoteFolder } from "../domain/types";
import { folderActions } from "../model/folders";
import type { LibraryPages } from "../model/library-resource";
import { deleteNote } from "../model/note-actions";
import { removeRecordingUpload, shownUploads, uploadRecordings, useRecordingUploads } from "../model/recording-uploads";
import { usePageDrop } from "../model/use-page-drop";
import { LoadMore } from "./load-more";
import { NoteContextMenu } from "./note-context-menu";
import { DraggableNote, NotesDndProvider } from "./notes-dnd";
import { NotesToolbar } from "./notes-toolbar";
import { EmptyFolder, EmptyLibrary, GridView, ListView, TimelineView } from "./notes-views";

interface NotesLibraryProps {
  readonly pages: LibraryPages;
  readonly folders: readonly NoteFolder[];
  /** Счётчики с сервера; null, пока они едут. */
  readonly counts: LibraryCounts | null;
  readonly activeFolderId: string | undefined;
  readonly view: NotesView;
}

const NO_COUNTS: ReadonlyMap<string, number> = new Map();

export function NotesLibrary({ pages, folders, counts, activeFolderId, view }: NotesLibraryProps) {
  const t = useTranslations("notes");
  const common = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const [editingId, setEditingId] = React.useState<string | null>(null);
  const recordings = useRecordingUploads();
  const zone = useTimeZone();
  const notesById = new Map(pages.items.map((note) => [note.id, note]));
  const { lead, others } = shownUploads(recordings, pages.items, hasFeaturedSlot(activeFolderId, view));
  const { featured, groups } = deriveLibrary(pages.items, activeFolderId, view, zone, lead !== undefined);

  const foldersById = new Map(folders.map((folder) => [folder.id, folder]));
  const folderOf = (note: MeetingCard) => (note.folderId ? foldersById.get(note.folderId) : undefined);
  const createFolder = async () => {
    const folder = await folderActions.create(t("folders.defaultName"), t);
    if (folder) setEditingId(folder.id);
    return folder;
  };
  const moveNote = (noteId: string, folderId: string | null) =>
    void folderActions.move(noteId, folderId ? (foldersById.get(folderId) ?? null) : null, t);
  const moveToNewFolder = async (noteId: string) => {
    const folder = await createFolder();
    if (folder) await folderActions.move(noteId, folder, t);
  };
  const deleteFolder = (id: string) => {
    void folderActions.remove(id, t);
    if (id === activeFolderId) router.push(buildNotesHref({ view }), { scroll: false });
  };
  const addRecordings = (files: File[]) => uploadRecordings(files, t);
  const drop = usePageDrop(addRecordings);

  // Во всех видах у каждой встречи одно и то же контекстное меню.
  const withMenu = (note: MeetingCard, content: React.ReactNode) => (
    <NoteContextMenu
      key={note.id}
      note={note}
      folders={folders}
      onMove={moveNote}
      onMoveToNewFolder={(noteId) => void moveToNewFolder(noteId)}
      onDelete={() => deleteNote(note, t, common)}
    >
      <DraggableNote noteId={note.id}>{content}</DraggableNote>
    </NoteContextMenu>
  );

  const dropOnFolder = (noteId: string, folderId: string | null) => {
    if (notesById.get(noteId)?.folderId !== (folderId ?? undefined)) moveNote(noteId, folderId);
  };

  const viewProps = { groups, recordings: others, folderOf, withMenu, onRemoveRecording: removeRecordingUpload };
  const isEmpty = !featured && !lead && groups.length === 0 && others.length === 0;

  return (
    <NotesDndProvider titleOf={(id) => notesById.get(id)?.title} onDropOnFolder={dropOnFolder}>
      <div className="flex min-h-[calc(100dvh-var(--dashboard-header-height)-3rem)] flex-col gap-8" {...drop.handlers}>
        <h1 className="sr-only">{t("meta.title")}</h1>
        <NotesToolbar
          folders={folders}
          activeFolderId={activeFolderId}
          view={view}
          totalCount={counts?.all ?? pages.items.length}
          countByFolder={counts?.byFolder ?? NO_COUNTS}
          editingId={editingId}
          onCreate={() => void createFolder()}
          onStartRename={setEditingId}
          onRename={(id, name) => {
            void folderActions.rename(id, name, t);
            setEditingId(null);
          }}
          onCancelRename={() => setEditingId(null)}
          onDelete={deleteFolder}
          onUpload={addRecordings}
        />

        {view === "timeline" ? <TimelineView {...viewProps} /> : null}
        {view === "grid" ? <GridView featured={featured} lead={lead} {...viewProps} /> : null}
        {view === "list" ? <ListView {...viewProps} /> : null}
        {isEmpty && activeFolderId ? <EmptyFolder /> : null}
        {isEmpty && !activeFolderId ? <EmptyLibrary /> : null}
        {pages.nextCursor === null ? null : <LoadMore folder={activeFolderId} />}

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
