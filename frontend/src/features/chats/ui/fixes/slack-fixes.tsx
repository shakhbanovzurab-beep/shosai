"use client";

import { useTransition } from "react";

import { toast } from "sonner";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { copyText } from "@/lib/copy-text";

import type { ChatConnection } from "../../domain/contract";
import { rejoinChat } from "../../model/connection-actions";
import { useSlackHandoff } from "../../model/slack-handoff";

/*
 * Починка канала Slack одним действием: вернуть Leo в открытый канал, скопировать команду приглашения в
 * закрытый, переподключить Slack, когда кончился доступ.
 */

export function RejoinChannel({ workspaceId, connection }: { workspaceId: string; connection: ChatConnection }) {
  const t = useTranslations("chats");
  const ta = useTranslations("chatsApi");
  const [busy, startTransition] = useTransition();
  const run = () =>
    startTransition(async () => {
      await rejoinChat(workspaceId, connection.id, t("fix.rejoined", { chat: connection.title }), ta);
    });
  return (
    <Button size="sm" variant="outline" disabled={busy} onClick={run}>
      {busy ? <Spinner data-icon="inline-start" /> : null}
      {t("fix.rejoin")}
    </Button>
  );
}

export function CopyInviteCommand({ app }: { app: string }) {
  const t = useTranslations("chats");
  const tc = useTranslations("chatsConnect");
  const copy = () =>
    copyText(`/invite @${app}`).then(
      () => toast.success(t("fix.inviteCopied")),
      () => toast.error(tc("copyFailed")),
    );
  return (
    <Button size="sm" variant="outline" onClick={() => void copy()}>
      {t("fix.copyInvite")}
    </Button>
  );
}

export function ReconnectSlack({ workspaceId, installationId }: { workspaceId: string; installationId: string }) {
  const t = useTranslations("chats");
  const tc = useTranslations("chatsConnect");
  const ta = useTranslations("chatsApi");
  const handoff = useSlackHandoff(workspaceId, { t: tc, ta }, () => toast.success(t("fix.slackReconnected")));
  return (
    <Button size="sm" variant="outline" disabled={handoff.waiting} onClick={() => void handoff.start(installationId)}>
      {handoff.waiting ? <Spinner data-icon="inline-start" /> : null}
      {t("fix.reconnectSlack")}
    </Button>
  );
}
