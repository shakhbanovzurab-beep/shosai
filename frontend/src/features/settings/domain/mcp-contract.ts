/* ---------- MCP servers: GET|POST /settings/mcp, PATCH|DELETE /settings/mcp/{id} ---------- */

export type McpTransport = "streamable_http" | "sse";

export type McpServer = {
  id: string;
  name: string;
  url: string;
  transport: McpTransport;
  enabled: boolean;
  /** Whether an Authorization header is stored; the value itself is never returned. */
  has_auth: boolean;
  /** Tools the server advertised the last time it was reached; null if it never answered. */
  tools: number | null;
};

export type McpServerDraft = { name: string; url: string; transport: McpTransport; auth_header: string };
export type McpServersResponse = { servers: McpServer[] };
