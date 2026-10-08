import { detail, JsonResponse } from "@/mocks/runtime";

import type { PlatformPromptDraft, PlatformPromptsState } from "../domain/contract";
import { configPatchSchema, publishSchema, restoreSchema } from "../domain/schema";
import { getState, patchDraft, publish, restore } from "./demo-store";

/* Route handlers for /api/admin/platform-prompts/*: the backend when configured, the in-memory demo otherwise. */

type VersionContext = { params: Promise<{ id: string }> };

/** /api/admin/platform-prompts */
export const platformPromptsRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<PlatformPromptsState>(getState());
  },
};

/** /api/admin/platform-prompts/draft */
export const platformPromptsDraftRoute = {
  async PATCH(request: Request) {
    const body = configPatchSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return detail(body.error.issues[0]?.message ?? "Некорректный черновик.", 422);
    return JsonResponse.json<PlatformPromptDraft>(patchDraft(body.data));
  },
};

/** /api/admin/platform-prompts/publish */
export const platformPromptsPublishRoute = {
  async POST(request: Request) {
    const body = publishSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return detail(body.error.issues[0]?.message ?? "Добавьте комментарий к версии.", 422);
    return JsonResponse.json<PlatformPromptsState>(publish(body.data.comment), { status: 201 });
  },
};

/** /api/admin/platform-prompts/versions/[id]/restore */
export const platformPromptVersionRestoreRoute = {
  async POST(request: Request, { params }: VersionContext) {
    const { id } = await params;
    const body = restoreSchema.safeParse((await request.json().catch(() => null)) ?? {});
    if (!body.success) return detail(body.error.issues[0]?.message ?? "Некорректный запрос.", 422);
    const state = restore(id, body.data.comment);
    return state ? JsonResponse.json<PlatformPromptsState>(state, { status: 201 }) : detail("Версия не найдена.", 404);
  },
};
