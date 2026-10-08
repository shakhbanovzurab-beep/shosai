import { ArrowLeft } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Link } from "@/lib/navigation";

import type { MeetingNote } from "../domain/types";
import { ActionItems } from "./action-items";
import { ExportTranscriptMenu } from "./export-transcript-menu";
import { MeetingFacts } from "./meeting-facts";
import { MyNotes } from "./my-notes";
import { NoteFolderPicker } from "./note-folder-picker";
import { NoteMindMap } from "./note-mind-map";
import { NoteParticipants } from "./note-participants";
import { type NoteTab, NoteTabs } from "./note-tabs";
import { SpeakerStats } from "./speaker-stats";
import { TranscriptSearch } from "./transcript-search";

interface NoteDetailProps {
  readonly note: MeetingNote;
  /** Extra actions next to the download button, e.g. sharing the recording to a workspace. */
  readonly actions?: React.ReactNode;
  /** Wraps the note's own action items, e.g. to show them as tasks once the recording is shared. */
  readonly renderActionItems?: (local: React.ReactNode) => React.ReactNode;
  /** More facts for the row under the title, e.g. the hub the meeting belongs to. */
  readonly meta?: React.ReactNode;
  /** Seconds into the recording a link pointed at: the transcript opens there. */
  readonly moment?: number;
}

const META_ROW = "flex min-h-6 flex-wrap items-center gap-x-5 gap-y-1 text-muted-foreground text-sm sm:flex-nowrap";

/** The tab a note opens on: the transcript at a linked moment, else the user's own notes, else Leo's. */
function initialTab(note: MeetingNote, moment: number | undefined): NoteTab {
  if (moment !== undefined) return "transcript";
  return note.myNotes ? "notes" : "enhanced";
}

export function NoteDetail({ note, actions, renderActionItems, meta, moment }: NoteDetailProps) {
  const t = useTranslations("notesNote");
  const localActionItems = note.actionItems.length > 0 ? <ActionItems items={note.actionItems} /> : null;
  const actionItems = localActionItems && renderActionItems ? renderActionItems(localActionItems) : localActionItems;

  return (
    <article className="mx-auto flex w-full max-w-3xl flex-col gap-6" aria-labelledby="note-title">
      <header className="flex flex-col gap-3">
        <Button variant="ghost" size="sm" className="-ms-2 w-fit text-muted-foreground" asChild>
          <Link href="/app/notes">
            <ArrowLeft data-icon="inline-start" className="rtl:-scale-x-100" />
            {t("back")}
          </Link>
        </Button>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <h1 id="note-title" dir="auto" className="text-2xl leading-tight tracking-tight">
            {note.title}
          </h1>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {actions}
            <ExportTranscriptMenu note={note} />
          </div>
        </div>
        {/* One row from sm up: the hub, last, is the only value that gives way, by truncating. */}
        <dl className={META_ROW}>
          <MeetingFacts startedAt={note.startedAt} durationMinutes={note.durationMinutes} />
          <NoteParticipants participants={note.participants} />
          <NoteFolderPicker noteId={note.id} initialFolderId={note.folderId} />
          {meta}
        </dl>
      </header>

      <NoteTabs
        defaultTab={initialTab(note, moment)}
        notes={<MyNotes noteId={note.id} />}
        enhanced={{ summary: note.summary, keyPoints: note.keyPoints, decisions: note.decisions, actionItems }}
        transcript={
          <div className="flex flex-col gap-6">
            <SpeakerStats note={note} />
            <TranscriptSearch lines={note.transcript} moment={moment} />
          </div>
        }
        mindMap={<NoteMindMap root={note.mindMap} />}
      />
    </article>
  );
}
