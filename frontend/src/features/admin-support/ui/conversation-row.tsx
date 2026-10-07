"use client";

import { cn } from "cn";
import { Lock, UserRound } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { pluralizeRu } from "@/lib/plural";
import { getInitials } from "@/lib/utils";

import type { Conversation } from "../domain/contract";
import { formatListTime } from "../domain/format";
import { ChannelLabel, PriorityLabel } from "./meta";

/** The last message for the row: notes get a lock, our replies a prefix. */
function preview({ author, kind, body }: Conversation["last_message"]) {
  const text = body || "Вложение";
  if (kind === "note") return { note: true, text };
  return { note: false, text: author === "agent" ? `Поддержка: ${text}` : text };
}

export function ConversationRow({
  conversation,
  selected,
  onSelect,
}: {
  conversation: Conversation;
  selected: boolean;
  onSelect: () => void;
}) {
  const { user, assignee, unread_count: unread } = conversation;
  const last = preview(conversation.last_message);
  const showUnread = unread > 0 && !selected;
  return (
    <li>
      <button
        type="button"
        onClick={onSelect}
        aria-current={selected ? "true" : undefined}
        className={cn(
          "flex w-full gap-3 rounded-lg px-3 py-2.5 text-left outline-none transition-colors hover:bg-muted/60 focus-visible:ring-2 focus-visible:ring-ring/50",
          selected && "bg-muted",
        )}
      >
        <Avatar className="mt-0.5">
          <AvatarFallback className="bg-muted text-foreground text-xs">{getInitials(user.name)}</AvatarFallback>
        </Avatar>
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="flex items-baseline gap-2">
            <span className={cn("min-w-0 flex-1 truncate text-sm", showUnread ? "font-semibold" : "font-medium")}>
              {user.name}
            </span>
            <time
              dateTime={conversation.last_message.created_at}
              className="shrink-0 text-muted-foreground text-xs tabular-nums"
            >
              {formatListTime(conversation.last_message.created_at)}
            </time>
          </span>
          <span className="flex items-center gap-2">
            <span
              className={cn(
                "line-clamp-1 min-w-0 flex-1 text-xs",
                showUnread ? "text-foreground" : "text-muted-foreground",
              )}
            >
              {last.note ? (
                <>
                  <Lock className="mr-1 inline size-3 align-[-1px]" aria-hidden="true" />
                  <span className="sr-only">Заметка: </span>
                </>
              ) : null}
              {last.text}
            </span>
            {showUnread ? (
              <Badge className="h-5 min-w-5 shrink-0 rounded-full px-1.5 tabular-nums">
                {unread}
                <span className="sr-only">
                  {" "}
                  {pluralizeRu(unread, ["непрочитанное", "непрочитанных", "непрочитанных"])}
                </span>
              </Badge>
            ) : null}
          </span>
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground text-xs">
            <ChannelLabel channel={conversation.channel} />
            <PriorityLabel priority={conversation.priority} />
            {assignee ? (
              <span className="inline-flex min-w-0 items-center gap-1 truncate">
                <UserRound className="size-3.5" aria-hidden="true" />
                <span className="sr-only">Ответственный: </span>
                {assignee.name}
              </span>
            ) : (
              <span>Не назначен</span>
            )}
          </span>
        </span>
      </button>
    </li>
  );
}
