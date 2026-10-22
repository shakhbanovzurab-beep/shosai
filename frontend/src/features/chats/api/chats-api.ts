import { apiRequest, jsonBody } from "@/lib/api/request";

import type {
  ChatConnection,
  ChatConnectionPatch,
  ChatConnectionsPage,
  ChatSettings,
  ChatSettingsPatch,
} from "../domain/contract";
import type { ConnectCode, ConnectCodeCreate, ConnectStatus } from "../domain/telegram-contract";

/*
 * Командные чаты пространства на `/v1/workspaces/{id}/chats*` (chats §1.2). Пока у слайса chats нет API, им
 * отвечают моки; потом шлюз переходит на сгенерированный клиент.
 */

const part = encodeURIComponent;

export function chatsApi(workspaceId: string) {
  const base = `/v1/workspaces/${part(workspaceId)}/chats`;
  const codes = `${base}/telegram/connect-codes`;
  return {
    settings: () => apiRequest<ChatSettings>(`${base}/settings`),
    patchSettings: (body: ChatSettingsPatch) => apiRequest<ChatSettings>(`${base}/settings`, jsonBody("PATCH", body)),
    list: () => apiRequest<ChatConnectionsPage>(base),
    patch: (id: string, body: ChatConnectionPatch) =>
      apiRequest<ChatConnection>(`${base}/${part(id)}`, jsonBody("PATCH", body)),
    remove: (id: string) => apiRequest<void>(`${base}/${part(id)}`, { method: "DELETE" }),
    rejoin: (id: string) => apiRequest<ChatConnection>(`${base}/${part(id)}/rejoin`, { method: "POST" }),
    createCode: (body: ConnectCodeCreate) => apiRequest<ConnectCode>(codes, jsonBody("POST", body)),
    pollCode: (id: string) => apiRequest<ConnectStatus>(`${codes}/${part(id)}`),
    cancelCode: (id: string) => apiRequest<void>(`${codes}/${part(id)}`, { method: "DELETE" }),
  };
}

export type ChatsApi = ReturnType<typeof chatsApi>;
