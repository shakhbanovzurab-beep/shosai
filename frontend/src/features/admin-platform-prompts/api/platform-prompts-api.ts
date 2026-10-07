import { apiRequest, jsonBody } from "@/lib/api-client";

import type {
  PlatformPromptConfigPatch,
  PlatformPromptDraft,
  PlatformPromptsState,
  PublishRequest,
  RestoreRequest,
} from "../domain/contract";

const BASE = "/api/admin/platform-prompts";

export const platformPromptsApi = {
  get: () => apiRequest<PlatformPromptsState>(BASE),
  saveDraft: (patch: PlatformPromptConfigPatch) =>
    apiRequest<PlatformPromptDraft>(`${BASE}/draft`, jsonBody("PATCH", patch)),
  publish: (body: PublishRequest) => apiRequest<PlatformPromptsState>(`${BASE}/publish`, jsonBody("POST", body)),
  restore: (id: string, body: RestoreRequest = {}) =>
    apiRequest<PlatformPromptsState>(`${BASE}/versions/${encodeURIComponent(id)}/restore`, jsonBody("POST", body)),
};
