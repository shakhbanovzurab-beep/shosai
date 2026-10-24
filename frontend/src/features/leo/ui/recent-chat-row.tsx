"use client";

import * as React from "react";

import { cn } from "cn";
import { MoreHorizontal } from "lucide-react";
import { toast } from "sonner";
import { useFormatter, useNow, useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { DropdownMenuItem } from "@/components/ui/dropdown-menu-items";
import { InputGroup, InputGroupInput } from "@/components/ui/input-group";

import type { AgentThread } from "../domain/agent-history";
import { RecentChatDelete } from "./recent-chat-delete";

// Название треда — от 1 до 120 символов (agent, `PATCH /v1/agent/threads/{id}`).
const TITLE_MAX = 120;

interface RecentChatRowProps {
  readonly thread: AgentThread;
  readonly current: boolean;
  readonly onSelect: (threadId: string) => void;
  readonly onRename: (threadId: string, title: string) => Promise<void>;
  readonly onRemove: (threadId: string) => Promise<void>;
}

/** Тред в «Недавних чатах»: открыть его, переименовать на месте или удалить после подтверждения. */
export function RecentChatRow({ thread, current, onSelect, onRename, onRemove }: RecentChatRowProps) {
  const t = useTranslations("leo");
  const common = useTranslations("common");
  const format = useFormatter();
  const now = useNow({ updateInterval: 60_000 });
  const [editing, setEditing] = React.useState(false);
  const [deleting, setDeleting] = React.useState(false);
  const title = thread.title ?? t("recent.untitled");

  const save = (value: string) => {
    setEditing(false);
    const next = value.trim();
    if (next === "" || next === thread.title) return;
    onRename(thread.id, next).catch(() => toast.error(t("recent.renameFailed")));
  };

  if (editing) {
    return (
      <li className="px-1 py-0.5">
        <InputGroup>
          <InputGroupInput
            aria-label={t("recent.titleLabel")}
            defaultValue={thread.title ?? ""}
            maxLength={TITLE_MAX}
            autoFocus
            onBlur={(event) => save(event.currentTarget.value)}
            onKeyDown={(event) => {
              // Правка кончается только через blur — название уходит один раз; Escape возвращает прежнее.
              if (event.key === "Escape") event.currentTarget.value = thread.title ?? "";
              if (event.key === "Enter" || event.key === "Escape") event.currentTarget.blur();
            }}
          />
        </InputGroup>
      </li>
    );
  }

  return (
    <li className={cn("flex items-center gap-1 rounded-md pe-1 hover:bg-muted", current && "bg-muted")}>
      <button
        type="button"
        aria-current={current ? "true" : undefined}
        onClick={() => onSelect(thread.id)}
        className="flex min-w-0 flex-1 cursor-pointer flex-col items-start rounded-md px-2 py-1.5 text-start outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="w-full truncate text-sm" dir="auto">
          {title}
        </span>
        <span className="text-muted-foreground text-xs">
          {format.relativeTime(new Date(thread.last_activity_at), now)}
        </span>
      </button>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-xs" aria-label={common("actionsFor", { name: title })}>
            <MoreHorizontal />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem onSelect={() => setEditing(true)}>{common("actions.renameMenu")}</DropdownMenuItem>
          <DropdownMenuItem variant="destructive" onSelect={() => setDeleting(true)}>
            {common("actions.delete")}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      <RecentChatDelete
        open={deleting}
        onOpenChange={setDeleting}
        onConfirm={() => onRemove(thread.id).catch(() => toast.error(t("recent.deleteFailed")))}
      />
    </li>
  );
}
