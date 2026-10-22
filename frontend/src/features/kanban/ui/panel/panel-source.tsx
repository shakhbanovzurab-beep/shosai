"use client";

import { ExternalLink, Video } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { MessengerMark } from "@/components/brand/messenger-mark";
import { Link } from "@/lib/navigation";

import type { TaskChatSource, TaskSource } from "../../domain/tasks-contract";

/**
 * Командный чат, из которого задача (TK-D13): «Из Telegram · „Release team“, 17 окт.» и ссылка на сообщение,
 * если она есть. Строка записана при создании, поэтому остаётся такой и после отключения чата.
 */
function ChatSource({ chat }: { chat: TaskChatSource }) {
  const t = useTranslations("kanbanPanel");
  const tk = useTranslations("kanban");
  const format = useFormatter();
  const messenger = tk(`card.messengers.${chat.messenger}`);
  const date = chat.message ? format.dateTime(new Date(chat.message.sent_at), "medium") : null;
  const title = () => <bdi>{chat.chat_title}</bdi>;
  return (
    <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-muted-foreground text-sm">
      <MessengerMark messenger={chat.messenger} className="shrink-0" />
      <span>
        {date
          ? t.rich("source.chatOn", { messenger, date, chat: title })
          : t.rich("source.chat", { messenger, chat: title })}
      </span>
      {chat.message?.url ? (
        <a
          href={chat.message.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-foreground underline-offset-4 hover:underline"
        >
          {t("source.openMessage")}
          <ExternalLink className="size-3.5 rtl:-scale-x-100" aria-hidden="true" />
        </a>
      ) : null}
    </p>
  );
}

/** Откуда задача: встреча со ссылкой на её страницу или что встречи больше нет (TK-D3); командный чат (TK-D13). */
export function PanelSource({ source }: { source: TaskSource }) {
  const t = useTranslations("kanbanPanel");
  const format = useFormatter();
  if (source.kind === "chat" && source.chat) return <ChatSource chat={source.chat} />;
  if (source.kind !== "meeting") return null;
  if (!source.meeting) return <p className="text-muted-foreground text-sm">{t("source.gone")}</p>;
  const date = format.dateTime(new Date(source.meeting.started_at), "medium");
  return (
    <p className="flex items-center gap-2 text-muted-foreground text-sm">
      <Video className="size-4 shrink-0" aria-hidden="true" />
      <Link
        href={`/app/notes/${encodeURIComponent(source.meeting.id)}`}
        className="underline-offset-4 hover:text-foreground hover:underline"
      >
        {t("source.meeting", { meeting: source.meeting.title, date })}
      </Link>
    </p>
  );
}
