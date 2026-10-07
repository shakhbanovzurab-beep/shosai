import { NextResponse } from "next/server";

import { detail, forwardToBackend } from "@/server/backend-proxy";

import type { PlatformPromptDraft, PlatformPromptsState } from "../domain/contract";
import { configPatchSchema, publishSchema, restoreSchema } from "../domain/schema";
import { getState, patchDraft, publish, restore } from "./demo-store";

/* Route handlers for /api/admin/platform-prompts/*: the backend when configured, the in-memory demo otherwise. */

type VersionContext = { params: Promise<{ id: string }> };

/** /api/admin/platform-prompts */
export const platformPromptsRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/admin/platform-prompts");
    if (upstream) return upstream;
    return NextResponse.json<PlatformPromptsState>(getState());
  },
};

/** /api/admin/platform-prompts/draft */
export const platformPromptsDraftRoute = {
  async PATCH(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/admin/platform-prompts/draft");
    if (upstream) return upstream;
    const body = configPatchSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return detail(body.error.issues[0]?.message ?? "Некорректный черновик.", 422);
    return NextResponse.json<PlatformPromptDraft>(patchDraft(body.data));
  },
};

/** /api/admin/platform-prompts/publish */
export const platformPromptsPublishRoute = {
  async POST(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/admin/platform-prompts/publish");
    if (upstream) return upstream;
    const body = publishSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return detail(body.error.issues[0]?.message ?? "Добавьте комментарий к версии.", 422);
    return NextResponse.json<PlatformPromptsState>(publish(body.data.comment), { status: 201 });
  },
};

/** /api/admin/platform-prompts/versions/[id]/restore */
export const platformPromptVersionRestoreRoute = {
  async POST(request: Request, { params }: VersionContext) {
    const { id } = await params;
    const upstream = await forwardToBackend(
      request,
      `/v1/admin/platform-prompts/versions/${encodeURIComponent(id)}/restore`,
    );
    if (upstream) return upstream;
    const body = restoreSchema.safeParse((await request.json().catch(() => null)) ?? {});
    if (!body.success) return detail(body.error.issues[0]?.message ?? "Некорректный запрос.", 422);
    const state = restore(id, body.data.comment);
    return state ? NextResponse.json<PlatformPromptsState>(state, { status: 201 }) : detail("Версия не найдена.", 404);
  },
};
