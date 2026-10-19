import { type MockRoute, mockRoute } from "@/mocks/routing";

import { acceptRoute, factRoute, factsRoute } from "./facts-route";

/** Память Leo для `npm run dev` и тестов — на путях бэкенда `/v1` (Leo §13.2), пока слайс `memory` не готов. */
export const handlers: MockRoute[] = [
  mockRoute("/v1/agent/memory", factsRoute, ["GET", "DELETE"]),
  mockRoute("/v1/agent/memory/:id", factRoute, ["PATCH", "DELETE"]),
  mockRoute("/v1/agent/memory/:id/accept", acceptRoute, ["POST"]),
];
