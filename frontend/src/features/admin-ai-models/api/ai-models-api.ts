import { apiRequest, jsonBody } from "@/lib/api-client";

import type { AiModel, AiModelPatch, AiModelsResponse, ConnectionCheckResponse } from "../domain/contract";

const BASE = "/api/admin/ai-models";

export const aiModelsApi = {
  list: () => apiRequest<AiModelsResponse>(BASE),
  patch: (id: string, patch: AiModelPatch) =>
    apiRequest<AiModel>(`${BASE}/${encodeURIComponent(id)}`, jsonBody("PATCH", patch)),
  check: () => apiRequest<ConnectionCheckResponse>(`${BASE}/check`, jsonBody("POST")),
};
