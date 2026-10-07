"use client";

import * as React from "react";

import { cn } from "cn";
import { MessagesSquare } from "lucide-react";

import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";

import { useInbox } from "../model/support-store";
import { ConversationList } from "./conversation-list";
import { ConversationView } from "./conversation-view";

const NO_SELECTION = (
  <Empty className="m-auto">
    <EmptyHeader>
      <EmptyMedia variant="icon">
        <MessagesSquare />
      </EmptyMedia>
      <EmptyTitle>Выберите разговор</EmptyTitle>
      <EmptyDescription>
        Здесь появится переписка с пользователем, его профиль и действия: назначение, статус и приоритет.
      </EmptyDescription>
    </EmptyHeader>
  </Empty>
);

/** Conversations on the left, the open one in the middle, the user's profile on the right; on phones they take turns. */
export function SupportInbox({ initialTicket }: { readonly initialTicket: string | null }) {
  const selectedId = useInbox((s) => s.selectedId);
  const select = useInbox((s) => s.select);

  // A link with `?ticket=` (e.g. from an issue on the errors page) opens that conversation once.
  React.useEffect(() => {
    if (initialTicket) select(initialTicket);
  }, [initialTicket, select]);

  return (
    <div className="grid h-[calc(100dvh-var(--dashboard-header-height))] min-h-0 grid-cols-1 overflow-hidden md:grid-cols-[20rem_minmax(0,1fr)]">
      <ConversationList className={cn(selectedId !== null && "max-md:hidden")} />
      <div className={cn("flex min-h-0 min-w-0 flex-col bg-muted/20", selectedId === null && "max-md:hidden")}>
        {selectedId === null ? NO_SELECTION : <ConversationView key={selectedId} id={selectedId} />}
      </div>
    </div>
  );
}
