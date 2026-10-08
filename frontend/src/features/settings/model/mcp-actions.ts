"use client";

import { toast } from "sonner";

import { apiErrorDescription } from "@/lib/api/error-description";
import { errorMessage } from "@/lib/errors";

import { settingsApi } from "../api/settings-api";
import type { McpServer, McpServerDraft } from "../domain/mcp-contract";
import { mcpResource } from "./settings-resources";
import type { McpWords } from "./words";

const replace = (server: McpServer) =>
  mcpResource.update((data) => ({ servers: data.servers.map((s) => (s.id === server.id ? server : s)) }));

/** Adds a remote MCP server; resolves to the error to show in the form, or null once it is added. */
export async function addMcpServer(draft: McpServerDraft, t: McpWords): Promise<string | null> {
  try {
    const server = await settingsApi.addMcp(draft);
    mcpResource.update((data) => ({ servers: [...data.servers, server] }));
    return null;
  } catch (error) {
    return errorMessage(error) ?? t("addFailed");
  }
}

export async function toggleMcpServer(server: McpServer, enabled: boolean, t: McpWords) {
  replace({ ...server, enabled });
  try {
    replace(await settingsApi.setMcpEnabled(server.id, enabled));
  } catch (error) {
    replace(server);
    toast.error(t("toggleFailed"), { description: apiErrorDescription(error) });
  }
}

export async function removeMcpServer(server: McpServer, t: McpWords) {
  try {
    await settingsApi.removeMcp(server.id);
    mcpResource.update((data) => ({ servers: data.servers.filter((s) => s.id !== server.id) }));
    toast.success(t("removed", { name: server.name }));
  } catch (error) {
    toast.error(t("removeFailed"), { description: apiErrorDescription(error) });
  }
}
