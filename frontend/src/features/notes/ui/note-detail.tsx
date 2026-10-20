import { ArrowLeft } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Link } from "@/lib/navigation";

import type { MeetingPage } from "../domain/meeting-page";
import { ExportTranscriptMenu } from "./export-transcript-menu";
import { MeetingFacts } from "./meeting-facts";
import { MyNotes } from "./my-notes";
import { MindMapPanel, TranscriptPanel } from "./note-content-panels";
import { NoteFolderPicker } from "./note-folder-picker";
import { NoteNotices } from "./note-notices";
import { NoteParticipants } from "./note-participants";
import { type NoteTab, NoteTabs } from "./note-tabs";

interface NoteDetailProps {
  readonly note: MeetingPage;
  /** Ещё действия рядом с кнопкой выгрузки, например поделиться записью с рабочим пространством. */
  readonly actions?: React.ReactNode;
  /** Оборачивает задачи встречи, например чтобы показать их задачами, когда записью поделились. */
  readonly renderActionItems?: (local: React.ReactNode) => React.ReactNode;
  /** Ещё факты в строку под заголовком, например хаб, к которому относится встреча. */
  readonly meta?: React.ReactNode;
  /** На какую секунду записи указывала ссылка: расшифровка открывается там. */
  readonly moment?: number;
}

const META_ROW = "flex min-h-6 flex-wrap items-center gap-x-5 gap-y-1 text-muted-foreground text-sm sm:flex-nowrap";

/** Вкладка, с которой открывается встреча: расшифровка у ссылки на момент, иначе запись Leo, а без неё — свои заметки. */
function initialTab(note: MeetingPage, moment: number | undefined): NoteTab {
  if (moment !== undefined) return "transcript";
  return note.notes === "ready" ? "enhanced" : "notes";
}

export function NoteDetail({ note, actions, renderActionItems, meta, moment }: NoteDetailProps) {
  const t = useTranslations("notesNote");

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
            {note.lineCount > 0 ? <ExportTranscriptMenu meetingId={note.id} /> : null}
          </div>
        </div>
        {/* С sm — одна строка: уступает место только последний хаб, обрезаясь. */}
        <dl className={META_ROW}>
          <MeetingFacts startedAt={note.startedAt} durationMinutes={note.durationMinutes} />
          <NoteParticipants note={note} />
          {note.owned ? <NoteFolderPicker noteId={note.id} folderId={note.folderId} /> : null}
          {meta}
        </dl>
        <NoteNotices note={note} />
      </header>

      <NoteTabs
        note={note}
        defaultTab={initialTab(note, moment)}
        notes={<MyNotes noteId={note.id} />}
        renderActionItems={renderActionItems}
        transcript={<TranscriptPanel note={note} moment={moment} />}
        mindMap={<MindMapPanel noteId={note.id} />}
      />
    </article>
  );
}
