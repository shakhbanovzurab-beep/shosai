"use client";

import { useTranslations } from "use-intl";

import { MessengerMark } from "@/components/brand/messenger-mark";

import type { CardChatSource } from "../../domain/tasks-contract";

/** Из какого командного чата задача (TK-D13): знак мессенджера и чат, без ссылки — она в панели (CF-D7). */
export function ChatSourceLine({ source }: { source: CardChatSource }) {
  const t = useTranslations("kanban");
  const name = t(`card.messengers.${source.messenger}`);
  return (
    <span className="flex min-w-0 items-center gap-1">
      <MessengerMark messenger={source.messenger} className="size-3.5 shrink-0" />
      <span className="sr-only">{t("card.fromChat", { messenger: name })}</span>
      <bdi title={source.chat_title} className="truncate">
        {source.chat_title}
      </bdi>
    </span>
  );
}
