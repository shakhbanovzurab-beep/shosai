"use client";
import { MessageSquareText } from "lucide-react";

import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { DropdownMenuItem, DropdownMenuLabel } from "@/components/ui/dropdown-menu-items";
import { InputGroupButton } from "@/components/ui/input-group";
import { Skeleton } from "@/components/ui/skeleton";
import { usePollingResource } from "@/hooks/use-polling-resource";

import { cannedRepliesResource } from "../model/support-store";

/** Saved answers; {name} becomes the user's first name. */
export function CannedReplies({ firstName, onInsert }: { firstName: string; onInsert: (text: string) => void }) {
  const state = usePollingResource(cannedRepliesResource);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <InputGroupButton size="sm" aria-label="Сохранённые ответы">
          <MessageSquareText />
          <span className="max-sm:hidden">Шаблоны</span>
        </InputGroupButton>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" side="top" className="w-72">
        <DropdownMenuLabel>Сохранённые ответы</DropdownMenuLabel>
        {state.status === "loading" ? <Skeleton className="m-1 h-16" /> : null}
        {state.status === "error" ? (
          <DropdownMenuItem onSelect={() => void cannedRepliesResource.refresh()}>
            Не удалось загрузить — повторить
          </DropdownMenuItem>
        ) : null}
        {state.status === "ready" && state.data.replies.length === 0 ? (
          <DropdownMenuItem disabled>Шаблонов пока нет</DropdownMenuItem>
        ) : null}
        {state.status === "ready"
          ? state.data.replies.map((reply) => (
              <DropdownMenuItem
                key={reply.id}
                className="flex-col items-start gap-0.5"
                onSelect={() => onInsert(reply.body.replaceAll("{name}", firstName))}
              >
                <span className="font-medium">{reply.title}</span>
                <span className="line-clamp-2 text-muted-foreground text-xs">
                  {reply.body.replaceAll("{name}", firstName)}
                </span>
              </DropdownMenuItem>
            ))
          : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
