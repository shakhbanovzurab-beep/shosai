import { apiRequest, jsonBody } from "@/lib/api/request";

import type { FactsPage, FactUpdate, MemoryFact } from "../domain/contract";

// Маршруты Leo §13.2; бэкенда `memory` ещё нет, и в OpenAPI их нет, поэтому запрос без сгенерированного клиента.
const BASE = "/v1/agent/memory";
const fact = (id: string) => `${BASE}/${encodeURIComponent(id)}`;

/** What Leo remembers (ADR 0030): list by pages, accept, edit or pin, forget one or all. */
export const memoryApi = {
  list: (cursor?: string): Promise<FactsPage> =>
    apiRequest(cursor ? `${BASE}?cursor=${encodeURIComponent(cursor)}` : BASE),
  update: (id: string, update: FactUpdate): Promise<MemoryFact> => apiRequest(fact(id), jsonBody("PATCH", update)),
  accept: (id: string): Promise<MemoryFact> => apiRequest(`${fact(id)}/accept`, { method: "POST" }),
  forget: (id: string): Promise<void> => apiRequest(fact(id), { method: "DELETE" }),
  forgetAll: (): Promise<void> => apiRequest(BASE, { method: "DELETE" }),
};
