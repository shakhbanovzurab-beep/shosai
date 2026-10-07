"use client";

import { Fragment } from "react";

import { ArrowDown } from "lucide-react";

import { Marker, MarkerContent } from "@/components/ui/marker";
import {
  MessageScroller,
  MessageScrollerButton,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller";

import type { SupportMessage } from "../domain/contract";
import { dayKey, formatDay, formatTime } from "../domain/format";
import type { OutboxItem } from "../model/support-store";
import { OutboxFooter, ReadStatus, ThreadMessage } from "./thread-message";

type ThreadMessagesProps = {
  messages: SupportMessage[];
  outbox: OutboxItem[];
  myName: string;
  onRetry: (localId: string) => void;
  onDiscard: (localId: string) => void;
};

/** The thread: the user on the left, the team on the right, notes in amber, events and days as separators. */
export function ThreadMessages({ messages, outbox, myName, onRetry, onDiscard }: ThreadMessagesProps) {
  const known = new Set(messages.map((m) => m.id));
  const pending = outbox.filter((item) => !(item.serverId && known.has(item.serverId)));

  return (
    <MessageScrollerProvider autoScroll>
      <MessageScroller className="min-h-0 flex-1">
        <MessageScrollerViewport aria-label="Переписка">
          <MessageScrollerContent className="mx-auto w-full max-w-3xl gap-5 px-4 py-6">
            {messages.map((message, index) => {
              const previous = messages[index - 1];
              const separator =
                previous && dayKey(previous.created_at) === dayKey(message.created_at) ? null : (
                  <Marker variant="separator">
                    <MarkerContent>{formatDay(message.created_at)}</MarkerContent>
                  </Marker>
                );
              if (message.author === "system") {
                return (
                  <Fragment key={message.id}>
                    {separator}
                    <Marker variant="separator">
                      <MarkerContent>
                        {message.body} · {formatTime(message.created_at)}
                      </MarkerContent>
                    </Marker>
                  </Fragment>
                );
              }
              return (
                <Fragment key={message.id}>
                  {separator}
                  <MessageScrollerItem messageId={message.id} scrollAnchor={message.author === "agent"}>
                    <ThreadMessage
                      message={{
                        author: message.author,
                        kind: message.kind,
                        name: message.author_name ?? "Пользователь",
                        body: message.body,
                        files: message.attachments,
                        createdAt: message.created_at,
                        footer:
                          message.author === "agent" && message.kind === "reply" ? (
                            <ReadStatus readAt={message.read_at} />
                          ) : null,
                      }}
                    />
                  </MessageScrollerItem>
                </Fragment>
              );
            })}
            {pending.map((item) => (
              <MessageScrollerItem key={item.localId} messageId={item.localId} scrollAnchor>
                <ThreadMessage
                  message={{
                    author: "agent",
                    kind: item.kind,
                    name: myName,
                    body: item.body,
                    files: item.attachments,
                    createdAt: item.created_at,
                    footer: (
                      <OutboxFooter
                        item={item}
                        onRetry={() => onRetry(item.localId)}
                        onDiscard={() => onDiscard(item.localId)}
                      />
                    ),
                  }}
                />
              </MessageScrollerItem>
            ))}
          </MessageScrollerContent>
        </MessageScrollerViewport>
        <MessageScrollerButton>
          <ArrowDown />
          <span className="sr-only">К последнему сообщению</span>
        </MessageScrollerButton>
      </MessageScroller>
    </MessageScrollerProvider>
  );
}
