"use client";

import { useTranslations } from "use-intl";

import { useWorkspace } from "@/features/workspace/model/use-workspace";
import { SettingsCard } from "@/features/workspace/ui/settings/setting-row";

import { useChatSettings, useConnections } from "../../model/resources";
import { AdminTeamChats } from "./admin-section";
import { ChatList, NoChats } from "./chat-list";
import { RetentionText, StorageRow } from "./storage-rows";

/*
 * «Командные чаты» в настройках пространства (ADR 0062): список подключённых чатов для всех участников,
 * подключение, изменение и срок хранения — для владельца и админов (`admin-section.tsx`).
 */

/** Участник видит список и срок хранения; менять их может только владелец или админ. */
function MemberTeamChats({ workspaceId }: { workspaceId: string }) {
  const t = useTranslations("chats");
  const settings = useChatSettings(workspaceId);
  const connections = useConnections(workspaceId);
  return (
    <SettingsCard id="chats" title={t("section.title")} description={t("section.description")}>
      <ChatList workspaceId={workspaceId} state={connections} empty={<NoChats hint={t("section.empty.member")} />} />
      {settings.status === "ready" ? (
        <StorageRow settings={settings.data} control={<RetentionText current={settings.data.retention_days} />} />
      ) : null}
    </SettingsCard>
  );
}

export function TeamChatsSection() {
  const { ws, can } = useWorkspace();
  return can.editSettings ? <AdminTeamChats workspaceId={ws} /> : <MemberTeamChats workspaceId={ws} />;
}
