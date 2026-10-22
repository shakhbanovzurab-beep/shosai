"use client";

import { useState } from "react";

import { Plus } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { useWorkspace } from "@/features/workspace/model/use-workspace";
import { SettingsCard } from "@/features/workspace/ui/settings/setting-row";
import { lazyComponent } from "@/lib/lazy-component";

import type { ChatSettings } from "../../domain/contract";
import { useChatSettings, useConnections } from "../../model/resources";
import { ChatList, NoChats } from "./chat-list";
import { RetentionControl, RetentionText, StorageRow } from "./storage-rows";

/*
 * «Командные чаты» в настройках пространства (ADR 0062): список подключённых чатов для всех участников,
 * подключение, изменение и срок хранения — для владельца и админов. Окно подключения — отдельный чанк,
 * который грузится, когда к кнопке подводят указатель или фокус.
 */

const loadConnect = () => import("../connect/connect-dialog");
const ConnectDialog = lazyComponent(() => loadConnect().then((m) => m.ConnectDialog));
const prefetchConnect = () => void loadConnect();

function ConnectButton({
  settings,
  full,
  onOpen,
}: {
  settings: ChatSettings | null;
  full: boolean;
  onOpen: () => void;
}) {
  const t = useTranslations("chats");
  return (
    <Button
      size="sm"
      disabled={settings === null || full}
      onPointerEnter={prefetchConnect}
      onFocus={prefetchConnect}
      onClick={onOpen}
    >
      <Plus data-icon="inline-start" />
      {t("section.connect")}
    </Button>
  );
}

export function TeamChatsSection() {
  const t = useTranslations("chats");
  const { ws, can } = useWorkspace();
  const settings = useChatSettings(ws);
  const connections = useConnections(ws);
  const [connecting, setConnecting] = useState(false);
  const admin = can.editSettings;
  const ready = settings.status === "ready" ? settings.data : null;
  const count = connections.status === "ready" ? connections.data.items.length : 0;
  const full = ready !== null && count >= ready.limits.connections;
  const empty = <NoChats hint={admin ? t("section.empty.admin") : t("section.empty.member")} />;

  return (
    <>
      <SettingsCard
        id="chats"
        title={t("section.title")}
        description={t("section.description")}
        action={admin ? <ConnectButton settings={ready} full={full} onOpen={() => setConnecting(true)} /> : null}
      >
        {admin && full ? <p className="pb-3 text-muted-foreground text-sm">{t("section.full", { count })}</p> : null}
        <ChatList workspaceId={ws} state={connections} empty={empty} />
        {ready ? (
          <StorageRow
            settings={ready}
            control={
              admin ? (
                <RetentionControl workspaceId={ws} current={ready.retention_days} />
              ) : (
                <RetentionText current={ready.retention_days} />
              )
            }
          />
        ) : null}
      </SettingsCard>
      {connecting && ready ? (
        <ConnectDialog workspaceId={ws} settings={ready} onClose={() => setConnecting(false)} />
      ) : null}
    </>
  );
}
