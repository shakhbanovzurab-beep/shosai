"use client";

import { useTransition } from "react";

import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

import type { ChatConnection } from "../../domain/contract";
import type { ConnectCodeCreate } from "../../domain/telegram-contract";
import { requestCode } from "../../model/chat-actions";
import { useReconnect } from "./reconnect-host";

/*
 * Починка группы Telegram новым кодом для того же чата (`connection_id`): Leo удалили — добавить снова;
 * Leo не админ — сделать админом (все права можно выключить, CF-D1). Код берётся по нажатию, окно держит раздел.
 */

function TelegramFix({
  workspaceId,
  connection,
  label,
  intro,
}: {
  workspaceId: string;
  connection: ChatConnection;
  label: string;
  intro: string;
}) {
  const ta = useTranslations("chatsApi");
  const [busy, startTransition] = useTransition();
  const reconnect = useReconnect();
  const start = () => startTransition(() => requestFor());
  const requestFor = async () => {
    const projectId = connection.binding.kind === "project" ? connection.binding.project.id : null;
    const request: ConnectCodeCreate = {
      project_id: projectId,
      mode: connection.mode,
      data_notice_accepted: true,
      connection_id: connection.id,
    };
    const code = await requestCode(workspaceId, request, ta);
    if (code) reconnect({ title: label, intro, request, code });
  };
  return (
    <Button size="sm" variant="outline" disabled={busy} onClick={start}>
      {busy ? <Spinner aria-hidden="true" data-icon="inline-start" /> : null}
      {label}
    </Button>
  );
}

export function AddLeoAgain({ workspaceId, connection }: { workspaceId: string; connection: ChatConnection }) {
  const t = useTranslations("chats");
  return (
    <TelegramFix
      workspaceId={workspaceId}
      connection={connection}
      label={t("fix.addAgain")}
      intro={t("fix.addAgainIntro", { chat: connection.title })}
    />
  );
}

export function MakeLeoAdmin({ workspaceId, connection }: { workspaceId: string; connection: ChatConnection }) {
  const t = useTranslations("chats");
  return (
    <TelegramFix
      workspaceId={workspaceId}
      connection={connection}
      label={t("fix.makeAdmin")}
      intro={t("fix.makeAdminIntro", { chat: connection.title })}
    />
  );
}
