import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

import type {
  ContextRoles,
  ModelsResponse,
  Prompt,
  PromptDraft,
  PromptsResponse,
  RoleModelSettings,
  StudioContext,
  StudioRole,
  UpdateRoleModelRequest,
} from "../domain/contract";

const prompt = (id: string) => ({ params: { path: { prompt_id: id } } });

/**
 * Studio человека на API (`/v1/studio/*`, токен человека). Создание промта идёт с ключом идемпотентности:
 * повтор с тем же ключом отвечает тем же промтом, а не создаёт второй.
 */
export const studioApi = {
  getContext: (): Promise<StudioContext> => dataOf(apiClient.GET("/v1/studio/context")),
  saveContext: (content: string): Promise<StudioContext> =>
    dataOf(apiClient.PUT("/v1/studio/context", { body: { content } })),
  saveContextRoles: (roles: ContextRoles): Promise<StudioContext> =>
    dataOf(apiClient.PUT("/v1/studio/context/roles", { body: { roles } })),

  listPrompts: (): Promise<PromptsResponse> => dataOf(apiClient.GET("/v1/studio/prompts")),
  createPrompt: (draft: PromptDraft, idempotencyKey: string): Promise<Prompt> =>
    dataOf(
      apiClient.POST("/v1/studio/prompts", {
        params: { header: { "Idempotency-Key": idempotencyKey } },
        body: draft,
      }),
    ),
  updatePrompt: (id: string, draft: Partial<PromptDraft>): Promise<Prompt> =>
    dataOf(apiClient.PATCH("/v1/studio/prompts/{prompt_id}", { ...prompt(id), body: draft })),
  deletePrompt: (id: string): Promise<unknown> =>
    dataOf(apiClient.DELETE("/v1/studio/prompts/{prompt_id}", prompt(id))),
  setActive: (role: StudioRole, promptId: string | null): Promise<PromptsResponse> =>
    dataOf(apiClient.PUT("/v1/studio/prompts/active", { body: { role, prompt_id: promptId } })),

  listModels: (): Promise<ModelsResponse> => dataOf(apiClient.GET("/v1/studio/models")),
  updateRole: (role: StudioRole, body: UpdateRoleModelRequest): Promise<RoleModelSettings> =>
    dataOf(apiClient.PUT("/v1/studio/models/roles/{role}", { params: { path: { role } }, body })),
};
