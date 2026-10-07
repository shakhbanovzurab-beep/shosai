"use client";

import type { ReactNode } from "react";

import { CircleCheck, Hash, Mail, MailOpen, MessageSquareText, Plus, RotateCcw, Text } from "lucide-react";
import { useTranslations } from "next-intl";
import { toast } from "sonner";

import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuSeparator,
  ContextMenuShortcut,
  ContextMenuTrigger,
} from "@/components/ui/context-menu";
import { copyText } from "@/lib/copy-text";

import type { Ticket, UpdateTicketRequest } from "../domain/contract";
import { useSupport } from "../model/support-store";
import { updateTicket } from "../model/ticket-actions";

async function copy(text: string, copied: string, failed: string) {
  try {
    await copyText(text);
    toast.success(copied);
  } catch {
    toast.error(failed);
  }
}

type TicketContextMenuProps = { ticket: Ticket; onOpen: (id: string) => void; children: ReactNode };

/** Right-click menu for a ticket row: open, read/unread, resolve/reopen, copy, new ticket. */
export function TicketContextMenu({ ticket, onOpen, children }: TicketContextMenuProps) {
  const t = useTranslations("pagesSupport");
  const tc = useTranslations("common");
  const select = useSupport((s) => s.select);
  const resolved = ticket.status === "resolved";

  const update = (patch: UpdateTicketRequest, done: string) => updateTicket(t, ticket.id, patch, done);

  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>{children}</ContextMenuTrigger>
      <ContextMenuContent className="w-56">
        <ContextMenuItem onSelect={() => onOpen(ticket.id)}>
          <MessageSquareText />
          {tc("actions.open")}
          <ContextMenuShortcut>↵</ContextMenuShortcut>
        </ContextMenuItem>
        <ContextMenuItem
          onSelect={() =>
            void update({ unread: !ticket.unread }, ticket.unread ? t("toasts.markedRead") : t("toasts.markedUnread"))
          }
        >
          {ticket.unread ? <MailOpen /> : <Mail />}
          {ticket.unread ? t("menu.markRead") : t("menu.markUnread")}
        </ContextMenuItem>
        <ContextMenuItem
          onSelect={() =>
            void update(
              { status: resolved ? "open" : "resolved" },
              resolved ? t("toasts.reopened") : t("toasts.resolved"),
            )
          }
        >
          {resolved ? <RotateCcw /> : <CircleCheck />}
          {resolved ? t("thread.reopen") : t("thread.resolve")}
        </ContextMenuItem>
        <ContextMenuSeparator />
        <ContextMenuItem
          onSelect={() => void copy(`#${ticket.number}`, t("toasts.numberCopied"), t("toasts.numberCopyFailed"))}
        >
          <Hash />
          {t("menu.copyNumber")}
        </ContextMenuItem>
        <ContextMenuItem
          onSelect={() => void copy(ticket.subject, t("toasts.subjectCopied"), t("toasts.subjectCopyFailed"))}
        >
          <Text />
          {t("menu.copySubject")}
        </ContextMenuItem>
        <ContextMenuSeparator />
        <ContextMenuItem onSelect={() => select("new")}>
          <Plus />
          {t("newTicket")}
        </ContextMenuItem>
      </ContextMenuContent>
    </ContextMenu>
  );
}
