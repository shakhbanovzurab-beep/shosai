import { apiRequest, jsonBody } from "@/lib/api-client";

import type { Connector, ConnectorId, ConnectorsResponse, ConnectResponse, IndexResponse } from "../domain/contract";

const request = <T>(path: string, init?: RequestInit) => apiRequest<T>(`/api/knowledge-base${path}`, init);

export const kbApi = {
  index: () => request<IndexResponse>("/index"),

  listConnectors: () => request<ConnectorsResponse>("/connectors"),
  connect: (id: ConnectorId, config: Record<string, string>) =>
    request<ConnectResponse>(`/connectors/${id}`, jsonBody("PUT", { config })),
  disconnect: (id: ConnectorId) => request<void>(`/connectors/${id}`, { method: "DELETE" }),
  sync: (id: ConnectorId) => request<Connector>(`/connectors/${id}/sync`, { method: "POST" }),
};
