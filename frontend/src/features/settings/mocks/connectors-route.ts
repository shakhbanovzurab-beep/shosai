import { z } from "zod";

import { JsonResponse } from "@/mocks/runtime";

import type { ConnectorsResponse, ConnectorUpdateResponse } from "../domain/connectors-contract";
import { beginAuthorization, completeAuthorization, disconnect, getConnector, listConnectors } from "./demo-connectors";
import { problemText, readJson, refuse } from "./problems";

type Context = { params: Promise<{ id: string }> };

/** /api/settings/connectors */
export const connectorsRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<ConnectorsResponse>({ connectors: listConnectors() });
  },
};

/** /api/settings/connectors/[id] */
export const connectorRoute = {
  async PATCH(request: Request, { params }: Context) {
    const { id } = await params;

    const body = z.object({ connected: z.boolean() }).safeParse(await readJson(request));
    if (!body.success) return refuse("invalidRequest", 422);

    if (!body.data.connected) {
      const connector = disconnect(id);
      if (!connector) return refuse("connectorNotFound", 404);
      return JsonResponse.json<ConnectorUpdateResponse>({ connector, authorize_url: null });
    }

    // Connecting starts OAuth: the connector stays as it is until the consent screen calls back.
    const connector = getConnector(id);
    const authorizeUrl = beginAuthorization(id);
    if (!connector || !authorizeUrl) return refuse("connectorNotFound", 404);
    return JsonResponse.json<ConnectorUpdateResponse>({ connector, authorize_url: authorizeUrl });
  },
};

/** /api/settings/connectors/[id]/callback */
export const connectorCallbackRoute = {
  /**
   * Demo stand-in for the backend's OAuth redirect URI: the demo consent page sends the user here with
   * `state` and the decision, and this finishes the connection and hands the popup to `/oauth/callback`.
   * With a real backend the provider calls the backend's own callback instead, so this is never used.
   */
  async GET(request: Request, { params }: Context) {
    const { id } = await params;
    const url = new URL(request.url);
    const state = url.searchParams.get("state") ?? "";
    const approved = url.searchParams.get("decision") === "allow";

    const result = completeAuthorization(id, state, approved);
    const next = new URLSearchParams({ connector: id, status: result.status });
    // The callback page shows the error as it comes, so it is worded here, in the request's language.
    if (result.error) next.set("error", await problemText(result.error));
    // A relative Location keeps the popup on the origin the user is on; behind a proxy or an IP,
    // the server's own idea of its origin (e.g. localhost) would break postMessage to the opener.
    return new Response(null, { status: 303, headers: { Location: `/oauth/callback?${next}` } });
  },
};
