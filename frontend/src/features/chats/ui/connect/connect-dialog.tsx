"use client";

import { useState } from "react";

import { ChevronRight } from "lucide-react";
import { useTranslations } from "use-intl";

import { MessengerTile } from "@/components/brand/messenger-mark";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

import type { ChatSettings, Messenger } from "../../domain/contract";
import { SlackConnect } from "./slack/slack-connect";
import { TelegramConnect } from "./telegram/telegram-connect";

/*
 * Окно «Подключить чат»: сначала мессенджер — только из тех, что обслуживает установка и для которых у
 * кабинета есть путь подключения; когда такой один, окно сразу открывается на нём.
 */

const FLOWS: readonly Messenger[] = ["telegram", "slack"];

function MessengerChoice({ choices, onPick }: { choices: Messenger[]; onPick: (messenger: Messenger) => void }) {
  const t = useTranslations("chatsConnect");
  const tc = useTranslations("chats");
  return (
    <div className="flex flex-col gap-2">
      {choices.map((messenger) => (
        <button
          key={messenger}
          type="button"
          data-messenger={messenger}
          onClick={() => onPick(messenger)}
          className="flex items-center gap-3 rounded-lg border p-3 text-start transition-colors hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
        >
          <MessengerTile messenger={messenger} />
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="font-medium">{tc(`messenger.${messenger}`)}</span>
            <span className="text-muted-foreground text-xs">{t(`choose.${messenger}`)}</span>
          </span>
          <ChevronRight aria-hidden="true" className="size-4 text-muted-foreground rtl:-scale-x-100" />
        </button>
      ))}
    </div>
  );
}

export function ConnectDialog({
  workspaceId,
  settings,
  onClose,
  onCloseAutoFocus,
}: {
  workspaceId: string;
  settings: ChatSettings;
  onClose: () => void;
  onCloseAutoFocus?: (event: Event) => void;
}) {
  const t = useTranslations("chatsConnect");
  const choices = settings.messengers.map((m) => m.messenger).filter((m) => FLOWS.includes(m));
  const [messenger, setMessenger] = useState<Messenger | null>(choices.length === 1 ? choices[0] : null);
  const bot = settings.messengers.find((m) => m.messenger === "telegram");
  const slack = settings.messengers.find((m) => m.messenger === "slack");

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-h-[90dvh] flex-col sm:max-w-lg" onCloseAutoFocus={onCloseAutoFocus}>
        <DialogHeader>
          <DialogTitle>{t("title")}</DialogTitle>
          <DialogDescription>{messenger === null ? t("choose.title") : t(`intro.${messenger}`)}</DialogDescription>
        </DialogHeader>
        {messenger === null ? <MessengerChoice choices={choices} onPick={setMessenger} /> : null}
        {messenger === "telegram" && bot?.messenger === "telegram" ? (
          <TelegramConnect workspaceId={workspaceId} settings={settings} bot={bot.bot_username} onDone={onClose} />
        ) : null}
        {messenger === "slack" && slack?.messenger === "slack" ? (
          <SlackConnect workspaceId={workspaceId} settings={settings} app={slack.app_name} onDone={onClose} />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
