"use client";

import { ChevronDown, UserRound } from "lucide-react";

import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import {
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu-items";

import {
  CONVERSATION_STATUSES,
  type ConversationDetail,
  type ConversationPriority,
  type ConversationStatus,
  PRIORITIES,
  type Teammate,
} from "../domain/contract";
import { PRIORITY_LABELS, STATUS_LABELS } from "../domain/labels";
import { updateConversation } from "../model/support-actions";
import { PriorityLabel } from "./meta";

const UNASSIGNED = "__none";

type ThreadActionsProps = {
  conversation: ConversationDetail;
  me: Teammate | null;
  teammates: Teammate[];
};

/** Assignee, status and priority for the open conversation; each change applies at once. */
export function ThreadActions({ conversation, me, teammates }: ThreadActionsProps) {
  const { id, assignee, status, priority } = conversation;

  const assign = (teammateId: string) => {
    const next = teammateId === UNASSIGNED ? null : (teammates.find((t) => t.id === teammateId) ?? null);
    void updateConversation(id, { assignee: next?.id ?? null }, { assignee: next });
  };

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" aria-label={`Ответственный: ${assignee?.name ?? "не назначен"}`}>
            <UserRound data-icon="inline-start" />
            <span className="max-w-32 truncate">{assignee?.name ?? "Не назначен"}</span>
            <ChevronDown data-icon="inline-end" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          {me && assignee?.id !== me.id ? (
            <>
              <DropdownMenuItem onSelect={() => assign(me.id)}>Назначить мне</DropdownMenuItem>
              <DropdownMenuSeparator />
            </>
          ) : null}
          <DropdownMenuLabel>Ответственный</DropdownMenuLabel>
          <DropdownMenuRadioGroup value={assignee?.id ?? UNASSIGNED} onValueChange={assign}>
            {teammates.map((teammate) => (
              <DropdownMenuRadioItem key={teammate.id} value={teammate.id}>
                {teammate.name}
                {teammate.id === me?.id ? <span className="text-muted-foreground"> (вы)</span> : null}
              </DropdownMenuRadioItem>
            ))}
            <DropdownMenuRadioItem value={UNASSIGNED}>Не назначен</DropdownMenuRadioItem>
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" aria-label={`Статус: ${STATUS_LABELS[status]}`}>
            {STATUS_LABELS[status]}
            <ChevronDown data-icon="inline-end" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>Статус</DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={status}
            onValueChange={(value) => {
              const next = value as ConversationStatus;
              void updateConversation(id, { status: next }, { status: next });
            }}
          >
            {CONVERSATION_STATUSES.map((value) => (
              <DropdownMenuRadioItem key={value} value={value}>
                {STATUS_LABELS[value]}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="outline" size="sm" aria-label={`Приоритет: ${PRIORITY_LABELS[priority]}`}>
            <PriorityLabel priority={priority} />
            <ChevronDown data-icon="inline-end" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel>Приоритет</DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={priority}
            onValueChange={(value) => {
              const next = value as ConversationPriority;
              void updateConversation(id, { priority: next }, { priority: next });
            }}
          >
            {PRIORITIES.map((value) => (
              <DropdownMenuRadioItem key={value} value={value}>
                <PriorityLabel priority={value} />
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
