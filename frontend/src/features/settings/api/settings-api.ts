import { apiRequest, jsonBody } from "@/lib/api-client";

import type {
  Billing,
  BillingPortalRequest,
  BillingPortalResponse,
  TopUpRequest,
  TopUpResponse,
  Usage,
} from "../domain/billing-contract";
import type { ConnectorsResponse, ConnectorUpdateResponse } from "../domain/connectors-contract";
import type { DataItemsResponse, DataKind } from "../domain/data-contract";
import type { McpServer, McpServerDraft, McpServersResponse } from "../domain/mcp-contract";
import type { MemorySummary } from "../domain/memory-contract";
import type {
  DeleteAccountRequest,
  DeleteAccountResponse,
  SettingsPatch,
  UserSettings,
} from "../domain/settings-contract";

const request = <T>(path: string, init?: RequestInit) => apiRequest<T>(`/api/settings${path}`, init);
const at = (base: string, id: string) => `${base}/${encodeURIComponent(id)}`;

export const settingsApi = {
  get: () => request<UserSettings>(""),
  patch: (patch: SettingsPatch) => request<UserSettings>("", jsonBody("PATCH", patch)),
  uploadAvatar: (image: Blob) => {
    const form = new FormData();
    form.append("file", image, "avatar");
    return request<UserSettings>("/avatar", { method: "PUT", body: form });
  },
  removeAvatar: () => request<UserSettings>("/avatar", { method: "DELETE" }),
  deleteAccount: (body: DeleteAccountRequest) =>
    request<DeleteAccountResponse>("/account/delete", jsonBody("POST", body)),
  listData: (kind: DataKind) => request<DataItemsResponse>(at("/data", kind)),
  deleteData: (kind: DataKind, id: string) => request<void>(at(at("/data", kind), id), { method: "DELETE" }),
  deleteAllData: (kind: DataKind) => request<void>(at("/data", kind), { method: "DELETE" }),
  billing: () => request<Billing>("/billing"),
  billingPortal: (body: BillingPortalRequest) =>
    request<BillingPortalResponse>("/billing/portal", jsonBody("POST", body)),
  usage: () => request<Usage>("/usage"),
  topUp: (body: TopUpRequest) => request<TopUpResponse>("/usage/top-up", jsonBody("POST", body)),
  listMcp: () => request<McpServersResponse>("/mcp"),
  addMcp: (draft: McpServerDraft) => request<McpServer>("/mcp", jsonBody("POST", draft)),
  setMcpEnabled: (id: string, enabled: boolean) => request<McpServer>(at("/mcp", id), jsonBody("PATCH", { enabled })),
  removeMcp: (id: string) => request<void>(at("/mcp", id), { method: "DELETE" }),
  listConnectors: () => request<ConnectorsResponse>("/connectors"),
  setConnected: (id: string, connected: boolean) =>
    request<ConnectorUpdateResponse>(at("/connectors", id), jsonBody("PATCH", { connected })),
  memorySummary: () => request<MemorySummary>("/memories/summary"),
  sendSummaryMessage: (message: string) => request<MemorySummary>("/memories/summary", jsonBody("POST", { message })),
  refreshSummary: () => request<MemorySummary>("/memories/summary/refresh", { method: "POST" }),
};
