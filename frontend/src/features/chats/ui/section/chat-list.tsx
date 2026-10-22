"use client";

import type { ReactNode } from "react";

import { MessagesSquare } from "lucide-react";
import { useTranslations } from "use-intl";

import { MessengerMark } from "@/components/brand/messenger-mark";
import { LoadError } from "@/components/feedback";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import type { ResourceState } from "@/lib/polling-resource";

import type { ChatConnection, ChatConnectionsPage } from "../../domain/contract";
import { chatResources } from "../../model/resources";
import { ConnectionRow } from "./chat-row";

/*
 * Список подключённых чатов в состояниях загрузки, ошибки и пустоты. Сервер уже упорядочил его: сначала то,
 * что требует внимания. Действия над строкой (для админов) приходят через `actionsFor`.
 */

const SKELETON_ROWS = ["a", "b", "c"];

function LoadingRows() {
  const t = useTranslations("common");
  return (
    <div role="status" aria-label={t("feedback.loading")} className="flex flex-col gap-4 pb-4">
      {SKELETON_ROWS.map((key) => (
        <div key={key} className="flex items-center gap-3">
          <Skeleton className="size-8 rounded-lg" />
          <div className="flex flex-1 flex-col gap-2">
            <Skeleton className="h-4 w-40" />
            <Skeleton className="h-3 w-64 max-w-full" />
          </div>
        </div>
      ))}
    </div>
  );
}

/** Пусто: что здесь появится и как начать; `hint` — свой для админа и участника. */
export function NoChats({ hint }: { hint: string }) {
  const t = useTranslations("chats");
  return (
    <Empty className="border-0 p-6">
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <MessagesSquare />
        </EmptyMedia>
        <EmptyTitle>{t("section.empty.title")}</EmptyTitle>
        <EmptyDescription>{hint}</EmptyDescription>
      </EmptyHeader>
      <div className="flex items-center gap-3 text-muted-foreground" aria-hidden="true">
        <MessengerMark messenger="telegram" />
        <MessengerMark messenger="slack" />
      </div>
    </Empty>
  );
}

export function ChatList({
  workspaceId,
  state,
  empty,
  actionsFor,
}: {
  workspaceId: string;
  state: ResourceState<ChatConnectionsPage>;
  /** Что показать, когда чатов нет. */
  empty: ReactNode;
  actionsFor?: (connection: ChatConnection) => ReactNode;
}) {
  const t = useTranslations("chats");
  const tc = useTranslations("common");
  if (state.status === "loading") return <LoadingRows />;
  if (state.status === "error")
    return (
      <LoadError
        title={t("section.loadError")}
        message={t("section.loadErrorHint")}
        retryLabel={tc("actions.retry")}
        onRetry={() => void chatResources(workspaceId).connections.refresh()}
      />
    );
  const { items } = state.data;
  if (items.length === 0) return empty;
  return (
    <ul aria-label={t("section.listLabel")} className="flex flex-col divide-y">
      {items.map((connection) => (
        <ConnectionRow key={connection.id} connection={connection} actions={actionsFor?.(connection)} />
      ))}
    </ul>
  );
}
