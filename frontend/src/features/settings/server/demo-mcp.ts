import type { McpServer, McpServerDraft } from "../domain/mcp-contract";

/* In-memory MCP servers for the demo; the auth header is kept out entirely, only its presence is recorded. */

const shared = globalThis as typeof globalThis & { settingsDemoMcp?: Map<string, McpServer> };
shared.settingsDemoMcp ??= new Map<string, McpServer>();
const store = shared.settingsDemoMcp;

export const listServers = () => [...store.values()];

export function addServer(draft: McpServerDraft): McpServer {
  const server: McpServer = {
    id: crypto.randomUUID(),
    name: draft.name,
    url: draft.url,
    transport: draft.transport,
    enabled: true,
    has_auth: draft.auth_header.trim().length > 0,
    tools: null,
  };
  store.set(server.id, server);
  return server;
}

export function setEnabled(id: string, enabled: boolean): McpServer | null {
  const server = store.get(id);
  if (!server) return null;
  const next = { ...server, enabled };
  store.set(id, next);
  return next;
}

export const removeServer = (id: string) => store.delete(id);
