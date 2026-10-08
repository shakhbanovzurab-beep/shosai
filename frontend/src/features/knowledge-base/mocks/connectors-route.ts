import { z } from "zod";

import { JsonResponse } from "@/mocks/runtime";

import type { ConnectorsResponse, ConnectResponse } from "../domain/contract";
import { connect, disconnect, listConnectors, syncNow } from "./demo-connectors";
import { isProblem, refuse } from "./problems";

type Context = { params: Promise<{ id: string }> };

const connectSchema = z.object({ config: z.record(z.string(), z.string().max(4000)) });

/** /api/knowledge-base/connectors */
export const connectorsRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<ConnectorsResponse>({ connectors: listConnectors() });
  },
};

/** /api/knowledge-base/connectors/[id] */
export const connectorRoute = {
  /** Saves the source's settings and starts its first sync. */
  async PUT(request: Request, { params }: Context) {
    const { id } = await params;

    const body = connectSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return refuse({ code: "invalidSettings" }, 422);
    const result = connect(id, body.data.config);
    if (result === null) return refuse({ code: "unknownSource" }, 404);
    if (isProblem(result)) return refuse(result, 422);
    return JsonResponse.json<ConnectResponse>({ connector: result, authorize_url: null });
  },

  async DELETE(_request: Request, { params }: Context) {
    const { id } = await params;
    return disconnect(id) ? new Response(null, { status: 204 }) : refuse({ code: "notConnected" }, 404);
  },
};

/** /api/knowledge-base/connectors/[id]/sync */
export const connectorSyncRoute = {
  async POST(_request: Request, { params }: Context) {
    const { id } = await params;
    const connector = syncNow(id);
    return connector ? JsonResponse.json(connector) : refuse({ code: "notConnected" }, 404);
  },
};
