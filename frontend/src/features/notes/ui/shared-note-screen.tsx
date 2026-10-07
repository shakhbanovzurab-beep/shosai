import { Circle, CircleCheck, Link2Off, Users } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";

import { MetaItem } from "@/components/meta-item";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";

import type { SharedNote } from "../domain/shared-note";
import { EnhancedNotes } from "./enhanced-notes";
import { MeetingFacts } from "./meeting-facts";
import { NoteTranscript } from "./note-transcript";
import { SharedComments } from "./shared-comments";
import { enhancedTemplate } from "./template-words";

const PAGE = "mx-auto flex w-full max-w-3xl flex-col gap-10 px-4 py-10 sm:py-16";

function SharedActionItems({ items }: { items: SharedNote["actionItems"] }) {
  const t = useTranslations("notesShare");
  return (
    <ul className="flex flex-col gap-2.5">
      {items.map((item) => (
        <li key={item.id} className="flex items-start gap-3 text-sm">
          {item.done ? (
            <CircleCheck className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-label={t("page.done")} />
          ) : (
            <Circle className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-label={t("page.open")} />
          )}
          <span className="flex min-w-0 flex-col gap-0.5">
            <span dir="auto">{item.text}</span>
            {item.owner ? (
              <span dir="auto" className="text-muted-foreground text-xs">
                {item.owner}
              </span>
            ) : null}
          </span>
        </li>
      ))}
    </ul>
  );
}

/** A meeting opened from a share link: Leo's notes, and the transcript and comments when the link allows them. */
export function SharedNoteScreen({ note }: { readonly note: SharedNote }) {
  const t = useTranslations("notesShare");
  const notes = useTranslations("notes");
  const templates = useTranslations("notesTemplates");
  const format = useFormatter();
  const people = note.participants
    ? format.list(
        note.participants.map((person) => person.name),
        { type: "unit", style: "short" },
      )
    : t("page.people", { count: note.participantCount });
  return (
    <main className={PAGE}>
      <header className="flex flex-col gap-3">
        <p className="text-muted-foreground text-sm">{t("page.eyebrow")}</p>
        <h1 dir="auto" className="text-balance text-3xl leading-tight tracking-tight">
          {note.title}
        </h1>
        <dl className="flex flex-wrap items-center gap-x-5 gap-y-1 text-muted-foreground text-sm">
          <MeetingFacts startedAt={note.startedAt} durationMinutes={note.durationMinutes} />
          <MetaItem icon={Users} label={notes("fields.participants")}>
            <span className="truncate">{people}</span>
          </MetaItem>
        </dl>
      </header>

      <EnhancedNotes
        template={enhancedTemplate(templates)}
        generating={false}
        content={{
          summary: note.summary,
          keyPoints: note.keyPoints,
          decisions: note.decisions,
          actionItems: note.actionItems.length > 0 ? <SharedActionItems items={note.actionItems} /> : null,
        }}
      />

      {note.transcript ? (
        <section aria-labelledby="shared-transcript-heading" className="flex flex-col gap-5 border-t pt-8">
          <h2 id="shared-transcript-heading" className="font-medium text-lg">
            {t("page.transcript")}
          </h2>
          <NoteTranscript lines={note.transcript} />
        </section>
      ) : null}

      {note.allowComments ? <SharedComments token={note.token} /> : null}
    </main>
  );
}

/** What an unknown, turned-off or expired link shows. */
export function SharedLinkGone() {
  const t = useTranslations("notesShare");
  return (
    <main className={PAGE}>
      <Empty>
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <Link2Off />
          </EmptyMedia>
          <EmptyTitle>{t("gone.title")}</EmptyTitle>
          <EmptyDescription>{t("gone.description")}</EmptyDescription>
        </EmptyHeader>
      </Empty>
    </main>
  );
}
