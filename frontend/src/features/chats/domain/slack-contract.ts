import type { ChatConnection, ChatMode, PersonRef } from "./contract";

/*
 * Slack (chats §1.1–§1.2): приложение ставят в пространство Slack через OAuth (передачу ведёт connectors),
 * потом выбирают каналы и привязку каждого. Shosai сам входит в открытые каналы; в закрытый Leo зовут
 * командой `/invite`.
 */

export type SlackInstallation = {
  id: string;
  team: { id: string; name: string; icon_url: string | null };
  installed_at: string;
  installed_by: PersonRef;
  state: "working" | "token_expired";
  /** Сколько каналов этой установки подключено. */
  connections: number;
};

export type SlackInstallationsResponse = { items: SlackInstallation[] };

/** Открытые каналы и закрытые, в которых Leo уже есть. */
export type SlackChannel = {
  id: string;
  name: string;
  private: boolean;
  member_count: number | null;
  leo_in_channel: boolean;
  connection_id: string | null;
};

export type SlackChannelsPage = { items: SlackChannel[]; next_cursor: string | null };

/** Начало OAuth: адрес экрана согласия для окна и срок его `state`. */
export type SlackHandoff = { authorize_url: string; expires_at: string };
export type SlackHandoffCreate = { installation_id?: string };

export type SlackConnect = {
  installation_id: string;
  channels: { channel_id: string; project_id: string | null }[];
  mode: ChatMode;
  data_notice_accepted: true;
};

export type SlackConnectResponse = { items: ChatConnection[] };

export const SLACK_CHANNELS_PER_CONNECT = 20;
export const SLACK_INSTALLATIONS_MAX = 10;
