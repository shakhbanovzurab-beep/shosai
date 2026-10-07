"use client";

import type { ReactNode } from "react";

import {
  Archive,
  AtSign,
  Check,
  Flag,
  FlagOff,
  Mail as MailIcon,
  MailOpen,
  PanelRightOpen,
  Pin,
  PinOff,
  Tag,
  Trash2,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { contextKit, type MenuKit } from "@/components/menu-kit";
import { ContextMenu, ContextMenuContent, ContextMenuTrigger } from "@/components/ui/context-menu";

import type { Mail } from "../domain/mail";
import { knownLabels, mailActions } from "../model/mail-store";
import { useMailWords } from "./use-mail-words";

/** Everything you can do to a message, for either the right-click menu or the inbox's "more" menu. */
export function MailMenuItems({ kit: K, mail, onOpen }: { kit: MenuKit; mail: Mail; onOpen?: () => void }) {
  const t = useTranslations("mail.menu");
  const common = useTranslations("common");
  const words = useMailWords();
  const applied = new Set(mail.labels);

  return (
    <>
      <K.Group>
        {onOpen ? (
          <K.Item onSelect={onOpen}>
            <PanelRightOpen className="rtl:-scale-x-100" />
            {common("actions.open")}
          </K.Item>
        ) : null}
        <K.Item onSelect={() => mailActions.toggleRead(mail.id)}>
          {mail.isRead ? <MailIcon /> : <MailOpen />}
          {mail.isRead ? t("markUnread") : t("markRead")}
        </K.Item>
        <K.Item onSelect={() => mailActions.togglePinned(mail.id)}>
          {mail.isPinned ? <PinOff /> : <Pin />}
          {mail.isPinned ? t("unpin") : t("pin")}
        </K.Item>
        <K.Item onSelect={() => mailActions.togglePriority(mail.id)}>
          {mail.isPriority ? <FlagOff /> : <Flag />}
          {mail.isPriority ? t("removePriority") : t("markPriority")}
        </K.Item>
        <K.Sub>
          <K.SubTrigger>
            <Tag />
            {t("labels")}
          </K.SubTrigger>
          <K.SubContent className="w-44">
            {knownLabels.map((label) => (
              <K.Item key={label} onSelect={() => mailActions.toggleLabel(mail.id, label)}>
                <Check className={applied.has(label) ? undefined : "invisible"} />
                <span dir="auto" className="capitalize">
                  {label}
                </span>
              </K.Item>
            ))}
          </K.SubContent>
        </K.Sub>
        <K.Item onSelect={() => mailActions.copySender(mail, words)}>
          <AtSign />
          {t("copySender")}
        </K.Item>
      </K.Group>
      <K.Separator />
      <K.Group>
        <K.Item onSelect={() => mailActions.moveTo(mail.id, "archive", words)}>
          <Archive />
          {t("archive")}
        </K.Item>
        <K.Item variant="destructive" onSelect={() => mailActions.moveTo(mail.id, "trash", words)}>
          <Trash2 />
          {t("trash")}
        </K.Item>
      </K.Group>
    </>
  );
}

/** Right-click (or long-press) a message in the list for its actions. */
export function MailContextMenu({ mail, onOpen, children }: { mail: Mail; onOpen: () => void; children: ReactNode }) {
  return (
    <ContextMenu>
      <ContextMenuTrigger asChild>{children}</ContextMenuTrigger>
      <ContextMenuContent className="w-56">
        <MailMenuItems kit={contextKit} mail={mail} onOpen={onOpen} />
      </ContextMenuContent>
    </ContextMenu>
  );
}
