import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";

import type {
  DraftPatch,
  PlatformDraft,
  PlatformPromptsState,
  PlatformVersion,
  VersionsPage,
} from "../domain/contract";

const VERSIONS_PAGE = 20;
const version = (id: string) => ({ path: { version_id: id } });
const key = (idempotencyKey: string) => ({ "Idempotency-Key": idempotencyKey });

/**
 * Экран промтов платформы на API studio (`/v1/admin/platform-prompts*`, сессия администратора). Публикация и откат
 * идут с ключом идемпотентности: повтор с тем же ключом отвечает той же версией, а не создаёт вторую.
 */
export const platformPromptsApi = {
  get: (): Promise<PlatformPromptsState> => dataOf(apiClient.GET("/v1/admin/platform-prompts")),
  saveDraft: (patch: DraftPatch): Promise<PlatformDraft> =>
    dataOf(apiClient.PATCH("/v1/admin/platform-prompts/draft", { body: patch })),
  publish: (comment: string, idempotencyKey: string): Promise<PlatformPromptsState> =>
    dataOf(
      apiClient.POST("/v1/admin/platform-prompts/publish", {
        params: { header: key(idempotencyKey) },
        body: { comment },
      }),
    ),
  versions: (cursor: string | null): Promise<VersionsPage> =>
    dataOf(
      apiClient.GET("/v1/admin/platform-prompts/versions", { params: { query: { limit: VERSIONS_PAGE, cursor } } }),
    ),
  version: (id: string): Promise<PlatformVersion> =>
    dataOf(apiClient.GET("/v1/admin/platform-prompts/versions/{version_id}", { params: version(id) })),
  restore: (id: string, idempotencyKey: string): Promise<PlatformPromptsState> =>
    dataOf(
      apiClient.POST("/v1/admin/platform-prompts/versions/{version_id}/restore", {
        params: { ...version(id), header: key(idempotencyKey) },
        body: { comment: "" },
      }),
    ),
};
