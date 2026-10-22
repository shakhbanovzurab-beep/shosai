"use client";

import { useState } from "react";

import { useTranslations } from "use-intl";

import { MessengerTile } from "@/components/brand/messenger-mark";
import { ConfirmDestructive } from "@/components/feedback";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import type { ChatConnection } from "../../domain/contract";
import type { SlackInstallation } from "../../domain/slack-contract";
import { removeInstallation } from "../../model/connection-actions";
import { useInstallations } from "../../model/resources";
import { ReconnectSlack } from "../fixes/slack-fixes";

/*
 * Пространства Slack, в которые поставлено приложение: по строке на каждое с числом каналов; админ отключает
 * его целиком — подтверждение называет каналы, сообщения которых сотрутся.
 */

function InstallationRow({
  workspaceId,
  item,
  channels,
}: {
  workspaceId: string;
  item: SlackInstallation;
  channels: string[];
}) {
  const t = useTranslations("chats");
  const ta = useTranslations("chatsApi");
  const [confirming, setConfirming] = useState(false);
  const body =
    channels.length > 0 ? t("installations.body", { channels: channels.join(", ") }) : t("installations.bodyEmpty");
  return (
    <li className="flex flex-wrap items-center gap-3 py-3 first:pt-0">
      <MessengerTile messenger="slack" />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="truncate font-medium text-sm">
          <bdi>{item.team.name}</bdi>
        </span>
        <span className="text-muted-foreground text-xs">
          {t("installations.channels", { count: item.connections })}
        </span>
      </span>
      {item.state === "token_expired" ? (
        <>
          <Badge variant="destructive">{t("state.needsAttention")}</Badge>
          <ReconnectSlack workspaceId={workspaceId} installationId={item.id} />
        </>
      ) : null}
      <Button size="sm" variant="ghost" onClick={() => setConfirming(true)}>
        {t("installations.disconnect")}
      </Button>
      <ConfirmDestructive
        open={confirming}
        title={t("installations.title", { team: item.team.name })}
        description={body}
        confirmLabel={t("disconnect.confirm")}
        onConfirm={() => {
          setConfirming(false);
          void removeInstallation(workspaceId, item, t("installations.done", { team: item.team.name }), ta);
        }}
        onCancel={() => setConfirming(false)}
      />
    </li>
  );
}

/** Подключённые пространства Slack — только админу и только когда они есть. */
export function SlackInstallations({
  workspaceId,
  connections,
}: {
  workspaceId: string;
  connections: ChatConnection[];
}) {
  const t = useTranslations("chats");
  const state = useInstallations(workspaceId);
  if (state.status !== "ready" || state.data.items.length === 0) return null;
  const channelsOf = (id: string) =>
    connections.filter((c) => c.slack?.installation_id === id).map((c) => `#${c.title}`);
  return (
    <div className="flex flex-col gap-2 py-4">
      <h3 className="font-medium text-sm">{t("installations.heading")}</h3>
      <ul className="flex flex-col divide-y">
        {state.data.items.map((item) => (
          <InstallationRow key={item.id} workspaceId={workspaceId} item={item} channels={channelsOf(item.id)} />
        ))}
      </ul>
    </div>
  );
}
