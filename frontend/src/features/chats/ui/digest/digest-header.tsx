"use client";

import { Info } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { MessengerTile } from "@/components/brand/messenger-mark";

import { type ChatDigest, DIGEST_MESSAGES_READ_MAX } from "../../domain/digest-contract";
import { type CoverageNote, coverageNotes, coveredFrom } from "../../domain/digest-rules";

/** Чат, период и сколько сообщений прочитано; название чата пишут люди, поэтому изолировано. */
export function DigestHeader({ digest }: { digest: ChatDigest }) {
  const t = useTranslations("chatsDigest");
  const format = useFormatter();
  const { chat, period, coverage } = digest;
  const title = chat.messenger === "slack" ? `#${chat.title}` : chat.title;
  return (
    <header className="flex items-center gap-3">
      <MessengerTile messenger={chat.messenger} />
      <div className="flex min-w-0 flex-col">
        <h3 title={title} className="truncate font-medium text-sm">
          <bdi>{title}</bdi>
        </h3>
        <p className="text-muted-foreground text-xs">
          {format.dateTimeRange(new Date(period.from), new Date(period.to), "short")}
          {" · "}
          {t("messagesRead", { count: coverage.messages_read })}
        </p>
      </div>
    </header>
  );
}

function NoteText({ note, digest }: { note: CoverageNote; digest: ChatDigest }) {
  const t = useTranslations("chatsDigest");
  const format = useFormatter();
  if (note.kind === "truncated") return t("coverage.truncated", { limit: DIGEST_MESSAGES_READ_MAX });
  const date = format.dateTime(new Date(note.from), "short");
  if (digest.chat.messenger === "slack") return t("coverage.slack", { date });
  const range = format.dateTimeRange(new Date(coveredFrom(digest)), new Date(digest.period.to), "short");
  return t("coverage.telegram", { date, range });
}

/** Оговорки о покрытии: о чём дайджест не может знать. */
export function CoverageNotes({ digest }: { digest: ChatDigest }) {
  const notes = coverageNotes(digest);
  if (notes.length === 0) return null;
  return (
    <div className="flex items-start gap-2 rounded-lg bg-muted/60 px-3 py-2 text-muted-foreground text-xs leading-relaxed">
      <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
      <div className="flex flex-col gap-1">
        {notes.map((note) => (
          <p key={note.kind}>
            <NoteText note={note} digest={digest} />
          </p>
        ))}
      </div>
    </div>
  );
}
