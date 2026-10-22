"use client";

import { useActionState, useState } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Dialog, DialogClose, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { FieldGroup } from "@/components/ui/field";
import { Spinner } from "@/components/ui/spinner";

import type { ChatConnection, ChatMode, ChatSettings } from "../../domain/contract";
import { changeChat } from "../../model/connection-actions";
import { BindingField, DataNotice, ModeField } from "../connect/connect-fields";

/*
 * Изменить привязку и режим чата. Переход на «Каждое сообщение» снова спрашивает согласие с хранением; в
 * Telegram после него чат ждёт, пока Leo сделают админом группы (CF-D1).
 */

export function ChangeChatDialog({
  workspaceId,
  settings,
  connection,
  onClose,
}: {
  workspaceId: string;
  settings: ChatSettings;
  connection: ChatConnection;
  onClose: () => void;
}) {
  const t = useTranslations("chats");
  const tc = useTranslations("common");
  const tconnect = useTranslations("chatsConnect");
  const ta = useTranslations("chatsApi");
  const initialProject = connection.binding.kind === "project" ? connection.binding.project.id : null;
  const [projectId, setProjectId] = useState<string | null>(initialProject);
  const [mode, setMode] = useState<ChatMode>(connection.mode);
  const [accepted, setAccepted] = useState(false);
  const needsNotice = mode === "all" && connection.mode !== "all";
  const app = settings.messengers.find((m) => m.messenger === "slack");
  const bot = settings.messengers.find((m) => m.messenger === "telegram");
  const hints =
    connection.messenger === "telegram"
      ? {
          mentions: tconnect("telegram.mentionsHint", { bot: bot?.messenger === "telegram" ? bot.bot_username : "" }),
          all: tconnect("telegram.allHint"),
        }
      : {
          mentions: tconnect("slack.mentionsHint", { app: app?.messenger === "slack" ? app.app_name : "" }),
          all: tconnect("slack.allHint"),
        };
  const [, submit, pending] = useActionState(async () => {
    const patch = { project_id: projectId, mode, ...(needsNotice ? { data_notice_accepted: accepted } : {}) };
    if (await changeChat(workspaceId, connection.id, patch, t("change.saved", { chat: connection.title }), ta))
      onClose();
    return null;
  }, null);

  return (
    <Dialog open onOpenChange={(open) => (open ? undefined : onClose())}>
      <DialogContent className="flex max-h-[90dvh] flex-col sm:max-w-lg">
        <form action={submit} className="flex min-h-0 flex-col gap-4">
          <DialogHeader>
            <DialogTitle>{t("change.title", { chat: connection.title })}</DialogTitle>
          </DialogHeader>
          <div className="-mx-1 flex min-h-0 flex-col overflow-y-auto px-1">
            <FieldGroup>
              <BindingField id="chat-change-binding" value={projectId} onChange={setProjectId} />
              <ModeField value={mode} onChange={setMode} hints={hints} />
              {needsNotice ? (
                <DataNotice mode={mode} settings={settings} checked={accepted} invalid={false} onChange={setAccepted} />
              ) : null}
            </FieldGroup>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button type="button" variant="outline">
                {tc("actions.cancel")}
              </Button>
            </DialogClose>
            <Button type="submit" disabled={pending || (needsNotice && !accepted)}>
              {pending ? <Spinner data-icon="inline-start" /> : null}
              {tc("actions.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
