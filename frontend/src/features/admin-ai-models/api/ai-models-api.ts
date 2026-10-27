import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

import type {
  AiModel,
  AiModelsResponse,
  ConnectionCheckResponse,
  ModelRole,
  RoleDefault,
  Tier,
  TierDecision,
} from "../domain/contract";

const model = (id: string) => ({ params: { path: { model_id: id } } });

/** Экран AI-моделей на API studio (`/v1/admin/ai-models*`, сессия администратора). */
export const aiModelsApi = {
  list: (): Promise<AiModelsResponse> => dataOf(apiClient.GET("/v1/admin/ai-models")),
  add: (openrouterId: string, tier: Tier | null): Promise<AiModel> =>
    dataOf(apiClient.POST("/v1/admin/ai-models", { body: { openrouter_id: openrouterId, tier } })),
  switch: (id: string, enabled: boolean): Promise<AiModel> =>
    dataOf(apiClient.PATCH("/v1/admin/ai-models/{model_id}", { ...model(id), body: { enabled } })),
  retire: (id: string): Promise<unknown> => dataOf(apiClient.DELETE("/v1/admin/ai-models/{model_id}", model(id))),
  decideTier: (id: string, decision: TierDecision): Promise<AiModel> =>
    dataOf(apiClient.POST("/v1/admin/ai-models/{model_id}/tier", { ...model(id), body: { decision } })),
  setDefault: (role: ModelRole, modelId: string, fallbackId: string | null): Promise<RoleDefault> =>
    dataOf(
      apiClient.PUT("/v1/admin/ai-models/defaults/{role}", {
        params: { path: { role } },
        body: { model_id: modelId, fallback_model_id: fallbackId },
      }),
    ),
  check: (): Promise<ConnectionCheckResponse> => dataOf(apiClient.POST("/v1/admin/ai-models/check")),
};
