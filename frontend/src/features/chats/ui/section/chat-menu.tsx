"use client";

import { useState } from "react";

import { EllipsisVertical, SlidersHorizontal, Unplug } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { ConfirmDestructive } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuItem, DropdownMenuSeparator } from "@/components/ui/dropdown-menu-items";

import type { ChatConnection, ChatSettings } from "../../domain/contract";
import { disconnectChat } from "../../model/connection-actions";
import { ChangeChatDialog } from "./change-dialog";

/*
 * Меню чата для админа: изменить привязку и режим, отключить. Отключение стирает сообщения, поэтому сначала
 * подтверждение, которое называет, сколько и с какого дня стирается и что задачи остаются.
 */

export function ChatMenu({
  workspaceId,
  settings,
  connection,
}: {
  workspaceId: string;
  settings: ChatSettings;
  connection: ChatConnection;
}) {
  const t = useTranslations("chats");
  const tc = useTranslations("common");
  const ta = useTranslations("chatsApi");
  const format = useFormatter();
  const [open, setOpen] = useState<"change" | "disconnect" | null>(null);
  const { messages, oldest_at: oldest } = connection.stored;
  const erased = oldest
    ? t("disconnect.body", { count: messages, since: format.dateTime(new Date(oldest), "short") })
    : t("disconnect.bodyEmpty");

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label={tc("actionsFor", { name: connection.title })}>
            <EllipsisVertical />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuGroup>
            <DropdownMenuItem onSelect={() => setOpen("change")}>
              <SlidersHorizontal />
              {t("menu.change")}
            </DropdownMenuItem>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            <DropdownMenuItem variant="destructive" onSelect={() => setOpen("disconnect")}>
              <Unplug />
              {t("menu.disconnect")}
            </DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      {open === "change" ? (
        <ChangeChatDialog
          workspaceId={workspaceId}
          settings={settings}
          connection={connection}
          onClose={() => setOpen(null)}
        />
      ) : null}
      <ConfirmDestructive
        open={open === "disconnect"}
        title={t("disconnect.title", { chat: connection.title })}
        description={erased}
        confirmLabel={t("disconnect.confirm")}
        onConfirm={() => {
          setOpen(null);
          void disconnectChat(workspaceId, connection, t("disconnect.done", { chat: connection.title }), ta);
        }}
        onCancel={() => setOpen(null)}
      />
    </>
  );
}
