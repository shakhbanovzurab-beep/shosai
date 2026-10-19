// Моки разработки слайса, по записи на путь. Чат — учебный `/api/leo` (NDJSON v1), предложения Leo — на путях
// бэкенда `/v1/agent/actions*` (Leo §13.2), пока слайс `agent` не опубликует API (F2-D1).
import { type MockRoute, mockRoute } from "@/mocks/routing";

import { leoRoute } from "./leo-route";
import { approveRoute, proposalsRoute, rejectRoute } from "./proposals-route";

export const handlers: MockRoute[] = [
  mockRoute("/api/leo", leoRoute, ["POST"]),
  mockRoute("/v1/agent/actions", proposalsRoute, ["GET"]),
  mockRoute("/v1/agent/actions/:id/approve", approveRoute, ["POST"]),
  mockRoute("/v1/agent/actions/:id/reject", rejectRoute, ["POST"]),
];
