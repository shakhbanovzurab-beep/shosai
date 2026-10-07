"use client";

import { cn } from "cn";
import { Inbox, UserRound } from "lucide-react";

import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Skeleton } from "@/components/ui/skeleton";
import { Toggle } from "@/components/ui/toggle";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { usePollingResource } from "@/hooks/use-polling-resource";

import { STATUS_FILTERS, type StatusFilter } from "../domain/contract";
import { FILTER_LABELS } from "../domain/labels";
import { listResource, useInbox } from "../model/support-store";
import { ConversationRow } from "./conversation-row";
import { PaneState } from "./pane-state";

const EMPTY_TEXT: Record<StatusFilter, string> = {
  open: "Нет открытых разговоров — все пользователи получили ответ.",
  pending: "Никто не ждёт ответа пользователя.",
  resolved: "Решённых разговоров пока нет.",
  all: "Пользователи ещё не писали в поддержку.",
};

const LIST_SKELETON = (
  <div className="flex flex-col gap-1 p-2" aria-hidden="true">
    {["a", "b", "c", "d", "e"].map((key) => (
      <Skeleton key={key} className="h-20 rounded-lg" />
    ))}
  </div>
);

/** Tabs by status, the «Мои» toggle, and the conversations for that filter. */
export function ConversationList({ className }: { className?: string }) {
  const { filter, mine, selectedId, setFilter, setMine, select } = useInbox();
  const resource = listResource(filter, mine);
  const state = usePollingResource(resource);
  const counts = state.status === "ready" ? state.data.counts : null;

  return (
    <section aria-labelledby="support-inbox-title" className={cn("flex min-h-0 flex-col border-r", className)}>
      <header className="flex flex-col gap-3 border-b px-3 py-3">
        <div className="flex items-center justify-between gap-2 px-1">
          <h2 id="support-inbox-title" className="font-semibold">
            Входящие
          </h2>
          <Toggle
            variant="outline"
            size="sm"
            pressed={mine}
            onPressedChange={setMine}
            aria-label="Только назначенные на меня"
          >
            <UserRound data-icon="inline-start" />
            Мои
          </Toggle>
        </div>
        <ToggleGroup
          type="single"
          size="sm"
          spacing={1}
          value={filter}
          onValueChange={(value) => {
            if (value) setFilter(value as StatusFilter);
          }}
          aria-label="Статус разговоров"
          className="flex-wrap"
        >
          {STATUS_FILTERS.map((status) => (
            <ToggleGroupItem
              key={status}
              value={status}
              className="data-[state=on]:bg-muted data-[state=on]:text-foreground"
            >
              {FILTER_LABELS[status]}
              {counts ? <span className="text-muted-foreground tabular-nums">{counts[status]}</span> : null}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain" aria-busy={state.status === "loading"}>
        <PaneState
          state={state}
          errorTitle="Не удалось загрузить разговоры"
          fallback={LIST_SKELETON}
          onRetry={() => void resource.refresh()}
        >
          {(data) =>
            data.conversations.length === 0 ? (
              <Empty className="h-full">
                <EmptyHeader>
                  <EmptyMedia variant="icon">
                    <Inbox />
                  </EmptyMedia>
                  <EmptyTitle>{mine ? "У вас нет разговоров" : "Здесь пусто"}</EmptyTitle>
                  <EmptyDescription>{EMPTY_TEXT[filter]}</EmptyDescription>
                </EmptyHeader>
              </Empty>
            ) : (
              <ul className="flex flex-col gap-0.5 p-2" aria-label={FILTER_LABELS[filter]}>
                {data.conversations.map((conversation) => (
                  <ConversationRow
                    key={conversation.id}
                    conversation={conversation}
                    selected={conversation.id === selectedId}
                    onSelect={() => select(conversation.id)}
                  />
                ))}
              </ul>
            )
          }
        </PaneState>
      </div>
    </section>
  );
}
