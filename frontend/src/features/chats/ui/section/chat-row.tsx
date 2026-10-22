"use client";

import type { ReactNode } from "react";

import { useFormatter, useNow, useTranslations } from "use-intl";

import { MessengerTile } from "@/components/brand/messenger-mark";
import { Badge } from "@/components/ui/badge";

import { problemWords } from "../../domain/chat-rules";
import type { ChatConnection } from "../../domain/contract";
import { useBindingText } from "../binding-text";

/*
 * Строка подключённого чата, из частей: знак, название, строка «привязка · режим · активность», проблема.
 * Работающий чат показывает только это; чат с проблемой — значок и слова (её действие — в части Problem).
 */

export function ChatRowRoot({ children }: { children: ReactNode }) {
  return <li className="flex items-start gap-3 py-3 first:pt-0">{children}</li>;
}

export function ChatRowBody({ children }: { children: ReactNode }) {
  return <div className="flex min-w-0 flex-1 flex-col gap-1">{children}</div>;
}

export function ChatRowTitle({ connection }: { connection: ChatConnection }) {
  const t = useTranslations("chats");
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
      <span className="sr-only">{t(`messenger.${connection.messenger}`)}</span>
      <span dir="auto" className="min-w-0 truncate font-medium text-sm">
        {connection.title}
      </span>
      {connection.state === "needs_attention" ? <Badge variant="destructive">{t("state.needsAttention")}</Badge> : null}
    </div>
  );
}

export function ChatRowMeta({ connection }: { connection: ChatConnection }) {
  const t = useTranslations("chats");
  const format = useFormatter();
  const now = useNow({ updateInterval: 60_000 });
  const bindingText = useBindingText();
  const activity = connection.last_activity_at
    ? t("activity.at", { when: format.relativeTime(new Date(connection.last_activity_at), now) })
    : t("activity.never");
  return (
    <p className="text-muted-foreground text-xs">
      {t("meta", { binding: bindingText(connection.binding), mode: t(`mode.${connection.mode}`), activity })}
    </p>
  );
}

/** Что сломалось — словами для группы или канала; `children` — одно действие, которое это чинит. */
export function ChatRowProblem({ connection, children }: { connection: ChatConnection; children?: ReactNode }) {
  const t = useTranslations("chats");
  const words = problemWords(connection);
  if (words === null) return null;
  return (
    <div className="flex flex-col gap-2 pt-1 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-destructive text-sm">{t(`problem.${words}`, { chat: connection.title })}</p>
      {children}
    </div>
  );
}

/** Строка чата целиком, как её видят участники; у админа своя строка из тех же частей (`admin-row.tsx`). */
export function ConnectionRow({ connection }: { connection: ChatConnection }) {
  return (
    <ChatRowRoot>
      <MessengerTile messenger={connection.messenger} />
      <ChatRowBody>
        <ChatRowTitle connection={connection} />
        <ChatRowMeta connection={connection} />
        <ChatRowProblem connection={connection} />
      </ChatRowBody>
    </ChatRowRoot>
  );
}
