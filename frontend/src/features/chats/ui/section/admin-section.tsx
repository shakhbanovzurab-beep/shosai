"use client";

import { useState } from "react";

import { useTranslations } from "use-intl";

import { SettingsCard } from "@/features/workspace/ui/settings/setting-row";

import type { ChatConnection, ChatConnectionsPage, ChatSettings } from "../../domain/contract";
import { useChatSettings, useConnections } from "../../model/resources";
import { ReconnectHost } from "../fixes/reconnect-host";
import { AdminConnectionRow } from "./admin-row";
import { ChatList, NoChats } from "./chat-list";
import { ConnectButton, ConnectDialog } from "./connect-button";
import { SlackInstallations } from "./installations";
import { RetentionControl, StorageRow } from "./storage-rows";

/*
 * «Командные чаты» для владельца и админов: подключение, строки с починкой и меню, пространства Slack и
 * выбор срока хранения. Пока настройки не пришли, подключать нечем — кнопка ждёт их.
 */

function AdminBody({
  workspaceId,
  settings,
  page,
}: {
  workspaceId: string;
  settings: ChatSettings;
  page: ChatConnectionsPage;
}) {
  const t = useTranslations("chats");
  const full = page.items.length >= settings.limits.connections;
  const row = (connection: ChatConnection) => (
    <AdminConnectionRow workspaceId={workspaceId} settings={settings} connection={connection} />
  );
  return (
    <ReconnectHost workspaceId={workspaceId}>
      {full ? (
        <p className="pb-3 text-muted-foreground text-sm">{t("section.full", { count: page.items.length })}</p>
      ) : null}
      <ChatList
        workspaceId={workspaceId}
        state={{ status: "ready", data: page, refreshing: false }}
        empty={<NoChats hint={t("section.empty.admin")} />}
        rowFor={row}
      />
      <SlackInstallations workspaceId={workspaceId} connections={page.items} />
    </ReconnectHost>
  );
}

export function AdminTeamChats({ workspaceId }: { workspaceId: string }) {
  const t = useTranslations("chats");
  const settings = useChatSettings(workspaceId);
  const connections = useConnections(workspaceId);
  const [connecting, setConnecting] = useState(false);
  const ready = settings.status === "ready" ? settings.data : null;
  const page = connections.status === "ready" ? connections.data : null;
  const full = ready !== null && page !== null && page.items.length >= ready.limits.connections;

  return (
    <>
      <SettingsCard
        id="chats"
        title={t("section.title")}
        description={t("section.description")}
        action={<ConnectButton settings={ready} full={full} onOpen={() => setConnecting(true)} />}
      >
        {ready && page ? (
          <AdminBody workspaceId={workspaceId} settings={ready} page={page} />
        ) : (
          <ChatList workspaceId={workspaceId} state={connections} empty={null} />
        )}
        {ready ? (
          <StorageRow
            settings={ready}
            control={<RetentionControl workspaceId={workspaceId} current={ready.retention_days} />}
          />
        ) : null}
      </SettingsCard>
      {connecting && ready ? (
        <ConnectDialog workspaceId={workspaceId} settings={ready} onClose={() => setConnecting(false)} />
      ) : null}
    </>
  );
}
