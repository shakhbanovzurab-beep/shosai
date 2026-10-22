import type { ChatConnectionsPage, ChatSettings } from "../../domain/contract";
import {
  connectionOf,
  connectionsOf,
  disconnect,
  findConnection,
  patchConnection,
  patchSettings,
  rejoin,
  settingsOf,
} from "../store/connections";
import { answer, bodyOf, type Ctx, inWorkspace, json, noContent, refuse } from "./http";
import { connectionPatchSchema, settingsPatchSchema } from "./schemas";

/* Настройки чатов пространства, список подключений, одно подключение, возврат Leo в канал (chats §1.2). */

const same = <T>(value: T) => value;

/** /v1/workspaces/[id]/chats/settings */
export const settingsRoute = {
  async GET(_request: Request, { params }: Ctx<"id">) {
    return inWorkspace(params, "member", (ws) => {
      const settings = settingsOf(ws);
      return settings ? json<ChatSettings>(settings) : refuse("workspace_not_found");
    });
  },
  async PATCH(request: Request, { params }: Ctx<"id">) {
    return inWorkspace(params, "admin", async (ws) => {
      const body = await bodyOf(request, settingsPatchSchema);
      if ("refusal" in body) return body.refusal;
      return answer(patchSettings(ws, body.data.retention_days), same);
    });
  },
};

/** /v1/workspaces/[id]/chats — не больше 50, поэтому одна страница. */
export const connectionsRoute = {
  async GET(_request: Request, { params }: Ctx<"id">) {
    return inWorkspace(params, "member", (ws) =>
      json<ChatConnectionsPage>({ items: connectionsOf(ws), next_cursor: null }),
    );
  },
};

const chatOf = async (params: Promise<Record<"id" | "chatId", string>>) => (await params).chatId;

/** /v1/workspaces/[id]/chats/[chatId] */
export const connectionRoute = {
  async GET(_request: Request, { params }: Ctx<"id" | "chatId">) {
    const chatId = await chatOf(params);
    return inWorkspace(params, "member", (ws) => {
      const connection = findConnection(ws, chatId);
      return connection ? json(connectionOf(connection)) : refuse("chat_not_found");
    });
  },
  async PATCH(request: Request, { params }: Ctx<"id" | "chatId">) {
    const chatId = await chatOf(params);
    return inWorkspace(params, "admin", async (ws) => {
      const connection = findConnection(ws, chatId);
      if (!connection) return refuse("chat_not_found");
      const body = await bodyOf(request, connectionPatchSchema);
      if ("refusal" in body) return body.refusal;
      return answer(patchConnection(connection, body.data), same);
    });
  },
  async DELETE(_request: Request, { params }: Ctx<"id" | "chatId">) {
    const chatId = await chatOf(params);
    return inWorkspace(params, "admin", (ws) => {
      const connection = findConnection(ws, chatId);
      if (!connection) return refuse("chat_not_found");
      disconnect(connection);
      return noContent();
    });
  },
};

/** /v1/workspaces/[id]/chats/[chatId]/rejoin */
export const rejoinRoute = {
  async POST(_request: Request, { params }: Ctx<"id" | "chatId">) {
    const chatId = await chatOf(params);
    return inWorkspace(params, "admin", (ws) => {
      const connection = findConnection(ws, chatId);
      return connection ? answer(rejoin(connection), same) : refuse("chat_not_found");
    });
  },
};
