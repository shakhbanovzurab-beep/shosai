import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import { apiRequest, jsonBody } from "@/lib/api/request";

import type {
  Billing,
  BillingPortalRequest,
  BillingPortalResponse,
  TopUpRequest,
  TopUpResponse,
  Usage,
} from "../domain/billing-contract";
import type { ConnectorsResponse, ConnectorUpdateResponse } from "../domain/connectors-contract";
import type { McpServer, McpServerDraft, McpServersResponse } from "../domain/mcp-contract";
import type { SettingsPatch, UserSettings } from "../domain/settings-contract";

const request = <T>(path: string, init?: RequestInit) => apiRequest<T>(`/api/settings${path}`, init);
const at = (base: string, id: string) => `${base}/${encodeURIComponent(id)}`;

export const settingsApi = {
  get: () => request<UserSettings>(""),
  patch: (patch: SettingsPatch) => request<UserSettings>("", jsonBody("PATCH", patch)),
  billing: () => request<Billing>("/billing"),
  billingPortal: (body: BillingPortalRequest) =>
    request<BillingPortalResponse>("/billing/portal", jsonBody("POST", body)),
  /** The week's tokens per tier and the frontier packs: the backend's (billing, step 6). */
  usage: (): Promise<Usage> => dataOf(apiClient.GET("/v1/settings/usage")),
  topUp: (body: TopUpRequest) => request<TopUpResponse>("/usage/top-up", jsonBody("POST", body)),
  listMcp: () => request<McpServersResponse>("/mcp"),
  addMcp: (draft: McpServerDraft) => request<McpServer>("/mcp", jsonBody("POST", draft)),
  setMcpEnabled: (id: string, enabled: boolean) => request<McpServer>(at("/mcp", id), jsonBody("PATCH", { enabled })),
  removeMcp: (id: string) => request<void>(at("/mcp", id), { method: "DELETE" }),
  listConnectors: () => request<ConnectorsResponse>("/connectors"),
  setConnected: (id: string, connected: boolean) =>
    request<ConnectorUpdateResponse>(at("/connectors", id), jsonBody("PATCH", { connected })),
};
