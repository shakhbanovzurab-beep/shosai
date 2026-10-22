"use client";

import { useTranslations } from "use-intl";

import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

import type { ConnectCode, ConnectCodeCreate } from "../../domain/telegram-contract";
import { AddBotStep } from "../connect/telegram/add-bot-step";

/* Окно починки группы Telegram: что сделать в Telegram и тот же шаг с кодом, что при подключении. */

export function ReconnectDialog({
  workspaceId,
  title,
  intro,
  request,
  code,
  onNewCode,
  onClose,
}: {
  workspaceId: string;
  title: string;
  intro: string;
  request: ConnectCodeCreate;
  code: ConnectCode;
  onNewCode: (code: ConnectCode) => void;
  onClose: () => void;
}) {
  const tc = useTranslations("common");
  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-h-[90dvh] flex-col sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{intro}</DialogDescription>
        </DialogHeader>
        <AddBotStep
          key={code.id}
          workspaceId={workspaceId}
          request={request}
          code={code}
          onNewCode={onNewCode}
          onBack={onClose}
          backLabel={tc("actions.close")}
          onDone={onClose}
        />
      </DialogContent>
    </Dialog>
  );
}
