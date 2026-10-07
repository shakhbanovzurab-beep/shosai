import { NextResponse } from "next/server";

import { z } from "zod";

import { forwardToBackend } from "@/server/backend-proxy";

import type { ConnectorsResponse, ConnectResponse } from "../domain/contract";
import { connect, disconnect, listConnectors, syncNow } from "./demo-connectors";
import { isProblem, refuse } from "./problems";

type Context = { params: Promise<{ id: string }> };

const connectSchema = z.object({ config: z.record(z.string(), z.string().max(4000)) });

/** /api/knowledge-base/connectors */
export const connectorsRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/knowledge-base/connectors");
    if (upstream) return upstream;
    return NextResponse.json<ConnectorsResponse>({ connectors: listConnectors() });
  },
};

/** /api/knowledge-base/connectors/[id] */
export const connectorRoute = {
  /** Saves the source's settings and starts its first sync. */
  async PUT(request: Request, { params }: Context) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, `/v1/knowledge-base/connectors/${encodeURIComponent(id)}`);
    if (upstream) return upstream;

    const body = connectSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return refuse({ code: "invalidSettings" }, 422);
    const result = connect(id, body.data.config);
    if (result === null) return refuse({ code: "unknownSource" }, 404);
    if (isProblem(result)) return refuse(result, 422);
    return NextResponse.json<ConnectResponse>({ connector: result, authorize_url: null });
  },

  async DELETE(request: Request, { params }: Context) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, `/v1/knowledge-base/connectors/${encodeURIComponent(id)}`);
    if (upstream) return upstream;
    return disconnect(id) ? new Response(null, { status: 204 }) : refuse({ code: "notConnected" }, 404);
  },
};

/** /api/knowledge-base/connectors/[id]/sync */
export const connectorSyncRoute = {
  async POST(request: Request, { params }: Context) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, `/v1/knowledge-base/connectors/${encodeURIComponent(id)}/sync`);
    if (upstream) return upstream;
    const connector = syncNow(id);
    return connector ? NextResponse.json(connector) : refuse({ code: "notConnected" }, 404);
  },
};
