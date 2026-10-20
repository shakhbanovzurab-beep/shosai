import type * as React from "react";

import { FolderOpen, NotebookPen } from "lucide-react";
import { useTranslations } from "use-intl";

import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";

import type { CardGroup, MeetingCard } from "../domain/library";
import type { NoteFolder } from "../domain/types";
import type { RecordingUpload } from "../model/recording-uploads";
import { FeaturedNoteCard, FeaturedRecordingCard } from "./featured-card";
import { NoteCard } from "./note-card";
import { NoteRow, NoteRowsHeader, RecordingRow } from "./note-row";
import { TimelineDay, TimelineEntry, TimelineRecording } from "./note-timeline";
import { RecordingCard } from "./recording-card";

export interface NotesViewProps {
  readonly groups: readonly CardGroup[];
  readonly recordings: readonly RecordingUpload[];
  readonly folderOf: (note: MeetingCard) => NoteFolder | undefined;
  readonly withMenu: (note: MeetingCard, content: React.ReactNode) => React.ReactNode;
  readonly onRemoveRecording: (id: string) => void;
}

export function TimelineView({ groups, recordings, folderOf, withMenu, onRemoveRecording }: NotesViewProps) {
  const t = useTranslations("notes");
  return (
    <div className="flex max-w-5xl flex-col gap-10">
      {recordings.length > 0 ? (
        <TimelineDay label={t("recordings.uploading")} dates={t("recordings.justNow")}>
          {recordings.map((recording) => (
            <TimelineRecording key={recording.id} recording={recording} onRemove={onRemoveRecording} />
          ))}
        </TimelineDay>
      ) : null}
      {groups.map((group) => (
        <TimelineDay key={group.recency} label={t(`recency.${group.recency}`)} notes={group.items}>
          {group.items.map((note) => (
            <li key={note.id}>{withMenu(note, <TimelineEntry note={note} folder={folderOf(note)} />)}</li>
          ))}
        </TimelineDay>
      ))}
    </div>
  );
}

interface GridViewProps extends NotesViewProps {
  readonly featured: MeetingCard | undefined;
  /** Загрузка в слоте последней встречи; остальные загрузки — в `recordings`. */
  readonly lead: RecordingUpload | undefined;
}

export function GridView({ featured, lead, groups, recordings, folderOf, withMenu, onRemoveRecording }: GridViewProps) {
  const t = useTranslations("notes");
  return (
    <div className="flex flex-col gap-8">
      {lead ? <FeaturedRecordingCard recording={lead} onRemove={onRemoveRecording} /> : null}
      {featured ? withMenu(featured, <FeaturedNoteCard note={featured} folder={folderOf(featured)} />) : null}
      {recordings.length > 0 ? (
        <CardSection label={t("recordings.uploading")}>
          {recordings.map((recording) => (
            <RecordingCard key={recording.id} recording={recording} onRemove={onRemoveRecording} />
          ))}
        </CardSection>
      ) : null}
      {groups.map((group) => (
        <CardSection key={group.recency} label={t(`recency.${group.recency}`)}>
          {group.items.map((note) => withMenu(note, <NoteCard note={note} folder={folderOf(note)} />))}
        </CardSection>
      ))}
    </div>
  );
}

export function ListView({ groups, recordings, folderOf, withMenu, onRemoveRecording }: NotesViewProps) {
  const t = useTranslations("notes");
  return (
    <div className="overflow-hidden rounded-2xl border bg-card">
      <NoteRowsHeader />
      {recordings.length > 0 ? (
        <RowSection label={t("recordings.uploading")}>
          {recordings.map((recording) => (
            <RecordingRow key={recording.id} recording={recording} onRemove={onRemoveRecording} />
          ))}
        </RowSection>
      ) : null}
      {groups.map((group) => (
        <RowSection key={group.recency} label={t(`recency.${group.recency}`)}>
          {group.items.map((note) => withMenu(note, <NoteRow note={note} folder={folderOf(note)} />))}
        </RowSection>
      ))}
    </div>
  );
}

function RowSection({ label, children }: { readonly label: string; readonly children: React.ReactNode }) {
  return (
    <section aria-label={label}>
      <h2 className="border-b bg-muted/40 px-4 py-1.5 font-medium text-muted-foreground text-xs">{label}</h2>
      <div className="divide-y border-b last:border-b-0">{children}</div>
    </section>
  );
}

function CardSection({ label, children }: { readonly label: string; readonly children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3" aria-label={label}>
      <h2 className="flex items-center gap-3 font-medium text-muted-foreground text-xs uppercase tracking-wider">
        {label}
        <span className="h-px flex-1 bg-border" aria-hidden="true" />
      </h2>
      <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">{children}</div>
    </section>
  );
}

export function EmptyFolder() {
  const t = useTranslations("notes");
  return (
    <Empty className="min-h-64 border border-dashed">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <FolderOpen />
        </EmptyMedia>
        <EmptyTitle>{t("folders.emptyTitle")}</EmptyTitle>
        <EmptyDescription>{t("folders.emptyDescription", { action: t("folders.moveTo") })}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}

/** Во всей библиотеке ещё нет встреч: откуда они появятся. */
export function EmptyLibrary() {
  const t = useTranslations("notes");
  return (
    <Empty className="min-h-64 border border-dashed">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <NotebookPen />
        </EmptyMedia>
        <EmptyTitle>{t("library.emptyTitle")}</EmptyTitle>
        <EmptyDescription>{t("library.emptyDescription")}</EmptyDescription>
      </EmptyHeader>
    </Empty>
  );
}
