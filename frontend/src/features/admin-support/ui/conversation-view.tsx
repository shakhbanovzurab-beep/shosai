"use client";

import { ArrowLeft, PanelRight, X } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Sheet, SheetClose, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { usePollingResource } from "@/hooks/use-polling-resource";
import { getInitials } from "@/lib/utils";

import type { ConversationDetail } from "../domain/contract";
import { discardMessage, retryMessage } from "../model/support-actions";
import { detailResource, listResource, type OutboxItem, useInbox } from "../model/support-store";
import { Composer } from "./composer";
import { ChannelLabel } from "./meta";
import { PaneState } from "./pane-state";
import { ThreadActions } from "./thread-actions";
import { ThreadMessages } from "./thread-messages";
import { UserProfile } from "./user-profile";

const NO_OUTBOX: OutboxItem[] = [];

const THREAD_SKELETON = (
  <div className="flex flex-1 flex-col gap-4 p-4" aria-hidden="true">
    <Skeleton className="h-12 rounded-lg" />
    <Skeleton className="h-20 w-2/3 rounded-xl" />
    <Skeleton className="ml-auto h-16 w-1/2 rounded-xl" />
    <Skeleton className="h-24 w-3/5 rounded-xl" />
  </div>
);

function Thread({ conversation }: { conversation: ConversationDetail }) {
  const { filter, mine, select, profileOpen, setProfileOpen } = useInbox();
  const outbox = useInbox((s) => s.outbox[conversation.id] ?? NO_OUTBOX);
  const list = usePollingResource(listResource(filter, mine));
  const me = list.status === "ready" ? list.data.me : null;
  const teammates = list.status === "ready" ? list.data.teammates : [];
  const { user } = conversation;

  return (
    <div className="flex min-h-0 flex-1">
      <section aria-labelledby="support-thread-title" className="flex min-h-0 min-w-0 flex-1 flex-col">
        <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b bg-background px-3 py-2.5">
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <Button
              variant="ghost"
              size="icon-sm"
              className="md:hidden"
              aria-label="К списку разговоров"
              onClick={() => select(null)}
            >
              <ArrowLeft />
            </Button>
            <Avatar className="max-sm:hidden">
              <AvatarFallback className="bg-muted text-foreground text-xs">{getInitials(user.name)}</AvatarFallback>
            </Avatar>
            <div className="flex min-w-0 flex-col">
              <h2 id="support-thread-title" className="truncate font-medium text-sm">
                {conversation.subject}
              </h2>
              <p className="flex min-w-0 items-center gap-1.5 truncate text-muted-foreground text-xs">
                <span className="truncate">{user.name}</span>
                <span aria-hidden="true">·</span>
                <span>#{conversation.number}</span>
                <span aria-hidden="true">·</span>
                <ChannelLabel channel={conversation.channel} />
              </p>
            </div>
          </div>
          <ThreadActions conversation={conversation} me={me} teammates={teammates} />
          <Button
            variant="ghost"
            size="icon-sm"
            className="xl:hidden"
            aria-label="Профиль пользователя"
            onClick={() => setProfileOpen(true)}
          >
            <PanelRight />
          </Button>
        </header>
        <ThreadMessages
          messages={conversation.messages}
          outbox={outbox}
          myName={me?.name ?? "Вы"}
          onRetry={(localId) => retryMessage(conversation.id, localId)}
          onDiscard={(localId) => discardMessage(conversation.id, localId)}
        />
        <Composer conversationId={conversation.id} userName={user.name} />
      </section>

      <aside aria-label="Профиль пользователя" className="hidden w-72 shrink-0 overflow-y-auto border-l xl:block">
        <UserProfile conversation={conversation} onOpenConversation={select} />
      </aside>

      <Sheet open={profileOpen} onOpenChange={setProfileOpen}>
        <SheetContent side="right" showCloseButton={false} className="gap-0 overflow-y-auto xl:hidden">
          <SheetHeader className="flex-row items-center justify-between border-b">
            <div>
              <SheetTitle>Профиль пользователя</SheetTitle>
              <SheetDescription className="sr-only">Данные пользователя и его обращения</SheetDescription>
            </div>
            <SheetClose asChild>
              <Button variant="ghost" size="icon-sm" aria-label="Закрыть">
                <X />
              </Button>
            </SheetClose>
          </SheetHeader>
          <UserProfile conversation={conversation} onOpenConversation={select} />
        </SheetContent>
      </Sheet>
    </div>
  );
}

/** One conversation: loads its thread (polled), then shows thread, composer and the user's profile. */
export function ConversationView({ id }: { id: string }) {
  const resource = detailResource(id);
  const state = usePollingResource(resource);
  const select = useInbox((s) => s.select);
  return (
    <>
      {state.status === "ready" ? null : (
        <div className="border-b px-3 py-2.5 md:hidden">
          <Button variant="ghost" size="sm" onClick={() => select(null)}>
            <ArrowLeft data-icon="inline-start" />К списку
          </Button>
        </div>
      )}
      <PaneState
        state={state}
        errorTitle="Не удалось открыть разговор"
        fallback={THREAD_SKELETON}
        onRetry={() => void resource.refresh()}
      >
        {(conversation) => <Thread conversation={conversation} />}
      </PaneState>
    </>
  );
}
