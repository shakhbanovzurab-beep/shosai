"use client";

import type { ChatConnection, ChatSettings } from "../../domain/contract";
import { CopyInviteCommand, ReconnectSlack, RejoinChannel } from "./slack-fixes";
import { AddLeoAgain, MakeLeoAdmin } from "./telegram-fix";

/*
 * Одно действие, которое чинит проблему чата (§3.4 плана): выбирается по проблеме, мессенджеру и виду канала.
 * Работающему чату чинить нечего.
 */

export function ProblemFix({
  workspaceId,
  settings,
  connection,
}: {
  workspaceId: string;
  settings: ChatSettings;
  connection: ChatConnection;
}) {
  const app = settings.messengers.find((m) => m.messenger === "slack");
  switch (connection.problem) {
    case null:
      return null;
    case "rights_missing":
      return <MakeLeoAdmin workspaceId={workspaceId} connection={connection} />;
    case "token_expired":
      return connection.slack ? (
        <ReconnectSlack workspaceId={workspaceId} installationId={connection.slack.installation_id} />
      ) : null;
    case "bot_not_in_chat":
      if (connection.messenger === "telegram") return <AddLeoAgain workspaceId={workspaceId} connection={connection} />;
      if (connection.kind === "public_channel")
        return <RejoinChannel workspaceId={workspaceId} connection={connection} />;
      return app?.messenger === "slack" ? <CopyInviteCommand app={app.app_name} /> : null;
  }
}
