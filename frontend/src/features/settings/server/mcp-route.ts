import { NextResponse } from "next/server";

import { z } from "zod";

import { forwardToBackend } from "@/server/backend-proxy";

import type { McpServer, McpServersResponse } from "../domain/mcp-contract";
import { addServer, listServers, removeServer, setEnabled } from "./demo-mcp";
import { firstIssue, type Problem, readJson, refuse } from "./problems";

const PATH = "/v1/settings/mcp";

// Messages are problem codes, worded for the request when it is refused (see ./problems).
const FIXABLE = ["mcpNameRequired", "mcpNameTooLong", "mcpUrlInvalid"] as const satisfies Problem[];
type Fixable = (typeof FIXABLE)[number];
const draftSchema = z.object({
  name: z
    .string()
    .trim()
    .min(1, "mcpNameRequired" satisfies Fixable)
    .max(60, "mcpNameTooLong" satisfies Fixable),
  url: z.url({ protocol: /^https?$/, error: "mcpUrlInvalid" satisfies Fixable }),
  transport: z.enum(["streamable_http", "sse"]),
  auth_header: z.string().max(4000),
});

type Context = { params: Promise<{ id: string }> };

/** /api/settings/mcp */
export const mcpServersRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, PATH);
    if (upstream) return upstream;
    return NextResponse.json<McpServersResponse>({ servers: listServers() });
  },

  async POST(request: Request) {
    const upstream = await forwardToBackend(request, PATH);
    if (upstream) return upstream;
    const body = draftSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error, FIXABLE), 422);
    return NextResponse.json<McpServer>(addServer(body.data), { status: 201 });
  },
};

/** /api/settings/mcp/[id] */
export const mcpServerRoute = {
  async PATCH(request: Request, { params }: Context) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, `${PATH}/${encodeURIComponent(id)}`);
    if (upstream) return upstream;
    const body = z.object({ enabled: z.boolean() }).safeParse(await readJson(request));
    if (!body.success) return refuse("invalidRequest", 422);
    const server = setEnabled(id, body.data.enabled);
    return server ? NextResponse.json(server) : refuse("mcpServerNotFound", 404);
  },

  async DELETE(request: Request, { params }: Context) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, `${PATH}/${encodeURIComponent(id)}`);
    if (upstream) return upstream;
    return removeServer(id) ? new Response(null, { status: 204 }) : refuse("mcpServerNotFound", 404);
  },
};
