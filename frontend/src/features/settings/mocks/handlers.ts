// Моки разработки слайса, по записи на путь. Использование — уже на путях бэкенда `/v1` (billing, шаг 6);
// остальное — учебные `/api/settings/*`, пока их слайсы не опубликуют API (F2-D1).
import { type MockRoute, mockRoute } from "@/mocks/routing";

import { billingPortalRoute, billingRoute, invoiceRoute, topUpRoute, usageRoute } from "./billing-route";
import { connectorCallbackRoute, connectorRoute, connectorsRoute } from "./connectors-route";
import { mcpServerRoute, mcpServersRoute } from "./mcp-route";
import { memoriesRoute, memoryRoute, memorySummaryRefreshRoute, memorySummaryRoute } from "./memory-route";
import { settingsRoute } from "./settings-route";

export const handlers: MockRoute[] = [
  mockRoute("/api/settings", settingsRoute, ["GET", "PATCH"]),
  mockRoute("/api/settings/billing", billingRoute, ["GET"]),
  mockRoute("/api/settings/billing/portal", billingPortalRoute, ["POST"]),
  mockRoute("/api/settings/connectors", connectorsRoute, ["GET"]),
  mockRoute("/api/settings/mcp", mcpServersRoute, ["GET", "POST"]),
  mockRoute("/api/settings/memories", memoriesRoute, ["GET", "DELETE"]),
  mockRoute("/api/settings/memories/summary", memorySummaryRoute, ["GET", "POST"]),
  mockRoute("/api/settings/memories/summary/refresh", memorySummaryRefreshRoute, ["POST"]),
  mockRoute("/v1/settings/usage", usageRoute, ["GET"]),
  mockRoute("/api/settings/usage/top-up", topUpRoute, ["POST"]),
  mockRoute("/api/settings/billing/invoices/:id", invoiceRoute, ["GET"]),
  mockRoute("/api/settings/connectors/:id", connectorRoute, ["PATCH"]),
  mockRoute("/api/settings/connectors/:id/callback", connectorCallbackRoute, ["GET"]),
  mockRoute("/api/settings/mcp/:id", mcpServerRoute, ["PATCH", "DELETE"]),
  mockRoute("/api/settings/memories/:id", memoryRoute, ["DELETE"]),
];
