import { apiRequest, jsonBody } from "@/lib/api/request";

import type {
  ModelsResponse,
  Prompt,
  PromptDraft,
  PromptsResponse,
  RoleModelSettings,
  SetActivePromptRequest,
  StudioContext,
  StudioRole,
  UpdateRoleModelRequest,
} from "../domain/contract";

const request = <T>(path: string, init?: RequestInit) => apiRequest<T>(`/api/studio${path}`, init);
const at = (base: string, id: string) => `${base}/${encodeURIComponent(id)}`;

export const studioApi = {
  getContext: () => request<StudioContext>("/context"),
  saveContext: (content: string) => request<StudioContext>("/context", jsonBody("PUT", { content })),

  listPrompts: () => request<PromptsResponse>("/prompts"),
  createPrompt: (draft: PromptDraft) => request<Prompt>("/prompts", jsonBody("POST", draft)),
  updatePrompt: (id: string, draft: Partial<PromptDraft>) =>
    request<Prompt>(at("/prompts", id), jsonBody("PATCH", draft)),
  deletePrompt: (id: string) => request<void>(at("/prompts", id), { method: "DELETE" }),
  setActive: (body: SetActivePromptRequest) => request<PromptsResponse>("/prompts/active", jsonBody("PUT", body)),

  listModels: () => request<ModelsResponse>("/models"),
  updateRole: (role: StudioRole, body: UpdateRoleModelRequest) =>
    request<RoleModelSettings>(`/models/roles/${role}`, jsonBody("PUT", body)),
};
