// Моки разработки слайса, по записи на путь. Использование — уже на путях бэкенда `/v1` (billing, шаг 6);
// остальное — учебные `/api/settings/*`, пока их слайсы не опубликуют API (F2-D1). Коннекторы — на API бэкенда.
import { type MockRoute, mockRoute } from "@/mocks/routing";

import { billingPortalRoute, billingRoute, invoiceRoute, topUpRoute, usageRoute } from "./billing-route";
import { mcpServerRoute, mcpServersRoute } from "./mcp-route";
import { settingsRoute } from "./settings-route";

export const handlers: MockRoute[] = [
  mockRoute("/api/settings", settingsRoute, ["GET", "PATCH"]),
  mockRoute("/api/settings/billing", billingRoute, ["GET"]),
  mockRoute("/api/settings/billing/portal", billingPortalRoute, ["POST"]),
  mockRoute("/api/settings/mcp", mcpServersRoute, ["GET", "POST"]),
  mockRoute("/v1/settings/usage", usageRoute, ["GET"]),
  mockRoute("/api/settings/usage/top-up", topUpRoute, ["POST"]),
  mockRoute("/api/settings/billing/invoices/:id", invoiceRoute, ["GET"]),
  mockRoute("/api/settings/mcp/:id", mcpServerRoute, ["PATCH", "DELETE"]),
];
