"use client";

import { cn } from "cn";
import { ExternalLink } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { getInitials } from "@/lib/utils";

import type { Messenger } from "../../domain/contract";
import type { ChatMessageRef, DigestItem, DigestPromise } from "../../domain/digest-contract";
import { ItemTaskAction } from "./digest-tasks";

/*
 * Пункт дайджеста: слова Leo, под ними — кто написал сообщение (по нажатию — само сообщение), когда и ссылка в
 * мессенджер; справа — задача из пункта. Обещание читается «кто · что · когда».
 */

const isPromise = (item: DigestItem): item is DigestPromise => "who" in item;

// Срок обещания — календарный день, полночь UTC: печатается в UTC и не сдвигается ни в каком поясе.
const DAY = { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" } as const;

/** Сообщение, из которого пункт: исходный текст людей, поэтому направление — по тексту. */
function QuoteButton({ message }: { message: ChatMessageRef }) {
  const t = useTranslations("chatsDigest");
  const format = useFormatter();
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button
          type="button"
          aria-label={t("item.quoteOf", { author: message.author_name })}
          className="max-w-48 truncate rounded-sm font-medium text-foreground/80 underline decoration-dotted underline-offset-4 hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
        >
          <bdi>{message.author_name}</bdi>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="flex w-80 flex-col gap-2 text-sm">
        <span className="text-muted-foreground text-xs">
          <bdi>{message.author_name}</bdi> · {format.dateTime(new Date(message.sent_at), "shortDateTime")}
        </span>
        <blockquote dir="auto" className="whitespace-pre-line border-s-2 ps-3 leading-relaxed">
          {message.quote}
        </blockquote>
      </PopoverContent>
    </Popover>
  );
}

/** Точка-разделитель внутри следующей части: при переносе строки она уходит вместе с ней. */
const Dot = () => (
  <span aria-hidden="true" className="me-1.5">
    ·
  </span>
);

function MessageMeta({ message, messenger }: { message: ChatMessageRef; messenger: Messenger }) {
  const t = useTranslations("chatsDigest");
  const tc = useTranslations("chats");
  const format = useFormatter();
  return (
    <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-muted-foreground text-xs">
      <QuoteButton message={message} />
      <span>
        <Dot />
        <time dateTime={message.sent_at}>{format.dateTime(new Date(message.sent_at), "shortDateTime")}</time>
      </span>
      {message.url ? (
        <span>
          <Dot />
          <a
            href={message.url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 underline-offset-4 hover:text-foreground hover:underline"
          >
            {t("item.openIn", { messenger: tc(`messenger.${messenger}`) })}
            <ExternalLink className="size-3 rtl:-scale-x-100" aria-hidden="true" />
          </a>
        </span>
      ) : null}
    </div>
  );
}

/** «Мария Чен · Обновить чек-лист релиза · ср, 24 окт.» сплошным текстом; аватар — у сопоставленного участника. */
function PromiseText({ promise }: { promise: DigestPromise }) {
  const format = useFormatter();
  const when = promise.due_on ? format.dateTime(new Date(promise.due_on), DAY) : promise.when_text;
  return (
    <>
      {promise.who.user_id ? (
        <Avatar aria-hidden="true" className="me-1.5 inline-flex size-5 align-text-bottom">
          <AvatarFallback className="text-[10px]">{getInitials(promise.who.name)}</AvatarFallback>
        </Avatar>
      ) : null}
      <bdi className="font-medium">{promise.who.name}</bdi>
      <span className="text-muted-foreground"> · </span>
      <span dir="auto">{promise.text}</span>
      {when ? <span className="text-muted-foreground"> · {when}</span> : null}
    </>
  );
}

export function DigestItemRow({ item, messenger }: { item: DigestItem; messenger: Messenger }) {
  const done = item.task_id !== null;
  return (
    <li className="flex @md:flex-row flex-col @md:items-start @md:gap-4 gap-2 py-3">
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className={cn("text-sm leading-relaxed", done && "text-muted-foreground")}>
          {isPromise(item) ? <PromiseText promise={item} /> : <span dir="auto">{item.text}</span>}
        </p>
        <MessageMeta message={item.message} messenger={messenger} />
      </div>
      <ItemTaskAction item={item} />
    </li>
  );
}
