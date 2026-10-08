"use client";

import { FileText } from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "use-intl";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Bubble, BubbleContent, BubbleGroup } from "@/components/ui/bubble";
import { Marker, MarkerContent } from "@/components/ui/marker";
import { Message, MessageAvatar, MessageContent, MessageFooter, MessageHeader } from "@/components/ui/message";
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller";
import { formatBytes } from "@/i18n/format-units";
import { getInitials } from "@/lib/utils";

import type { TicketAttachment, TicketMessage } from "../domain/contract";

/*
 * Message times are the viewer's own wall clock, not UTC: the thread is fetched and drawn in the browser
 * only (the store starts empty on the server), so formatting in the browser's time zone can't mismatch.
 */
const viewerTimeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

function Attachments({ files }: { files: TicketAttachment[] }) {
  const locale = useLocale();
  if (files.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-1.5">
      {files.map((file) => (
        <li key={file.name} className="flex items-center gap-1.5 rounded-md border bg-background px-2 py-1 text-xs">
          <FileText className="size-3.5 text-muted-foreground" aria-hidden="true" />
          {file.url ? (
            <a
              href={file.url}
              target="_blank"
              rel="noreferrer"
              dir="auto"
              className="underline-offset-2 hover:underline"
            >
              {file.name}
            </a>
          ) : (
            <span dir="auto">{file.name}</span>
          )}
          <span className="text-muted-foreground">{formatBytes(locale, file.size_bytes)}</span>
        </li>
      ))}
    </ul>
  );
}

function PersonMessage({ message }: { message: TicketMessage }) {
  const t = useTranslations("pagesSupport");
  const format = useFormatter();
  const mine = message.author === "you";
  const sender = message.author_name ?? t("thread.support");
  return (
    <Message align={mine ? "end" : "start"}>
      {mine ? null : (
        <MessageAvatar>
          <Avatar>
            <AvatarFallback className="bg-muted text-foreground text-xs">{getInitials(sender)}</AvatarFallback>
          </Avatar>
        </MessageAvatar>
      )}
      <MessageContent>
        {mine ? null : (
          <MessageHeader className="text-muted-foreground text-xs">
            {t("thread.supportAuthor", { name: sender })}
          </MessageHeader>
        )}
        {message.body ? (
          <BubbleGroup>
            <Bubble variant={mine ? "default" : "muted"} align={mine ? "end" : "start"}>
              <BubbleContent dir="auto" className="whitespace-pre-line">
                {message.body}
              </BubbleContent>
            </Bubble>
          </BubbleGroup>
        ) : null}
        <Attachments files={message.attachments} />
        <MessageFooter>
          {format.dateTime(new Date(message.created_at), "shortDateTime", { timeZone: viewerTimeZone() })}
        </MessageFooter>
      </MessageContent>
    </Message>
  );
}

/** A system event as a quiet separator, worded from its code when the backend sends one. */
function EventMarker({ message }: { message: TicketMessage }) {
  const t = useTranslations("pagesSupport");
  const format = useFormatter();
  const event = message.event ? t(`events.${message.event}`) : message.body;
  const date = format.dateTime(new Date(message.created_at), "short", { timeZone: viewerTimeZone() });
  return (
    <Marker variant="separator">
      <MarkerContent dir={message.event ? undefined : "auto"}>{t("thread.event", { event, date })}</MarkerContent>
    </Marker>
  );
}

/** The thread: your messages at the end side, support's at the start, events as quiet separators. */
export function TicketMessages({ messages }: { messages: TicketMessage[] }) {
  return (
    <MessageScrollerProvider autoScroll>
      <MessageScroller className="min-h-0 flex-1">
        <MessageScrollerViewport>
          <MessageScrollerContent className="mx-auto w-full max-w-3xl gap-5 px-4 py-6">
            {messages.map((message) =>
              message.author === "system" ? (
                <EventMarker key={message.id} message={message} />
              ) : (
                <MessageScrollerItem key={message.id} messageId={message.id} scrollAnchor={message.author === "you"}>
                  <PersonMessage message={message} />
                </MessageScrollerItem>
              ),
            )}
          </MessageScrollerContent>
        </MessageScrollerViewport>
        <MessageScrollerButton />
      </MessageScroller>
    </MessageScrollerProvider>
  );
}
