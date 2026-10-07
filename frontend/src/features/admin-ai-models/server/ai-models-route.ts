import { NextResponse } from "next/server";

import { detail, forwardToBackend } from "@/server/backend-proxy";

import {
  type AiModel,
  type AiModelsResponse,
  aiModelPatchSchema,
  type ConnectionCheckResponse,
} from "../domain/contract";
import { checkConnection, getAiModels, patchAiModel } from "./ai-models";

type Context = { params: Promise<{ id: string }> };

/** `/api/admin/ai-models`: provider status, spend and the model catalogue. */
export const aiModelsRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/admin/ai-models");
    if (upstream) return upstream;
    return NextResponse.json<AiModelsResponse>(await getAiModels());
  },
};

/** `/api/admin/ai-models/check`: reaches OpenRouter with the server's key. */
export const aiModelsCheckRoute = {
  async POST(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/admin/ai-models/check");
    if (upstream) return upstream;
    return NextResponse.json<ConnectionCheckResponse>(await checkConnection());
  },
};

/** `/api/admin/ai-models/{id}`: switches a model on or off, or makes it the default. */
export const aiModelRoute = {
  async PATCH(request: Request, { params }: Context) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, `/v1/admin/ai-models/${encodeURIComponent(id)}`);
    if (upstream) return upstream;
    const body = aiModelPatchSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return detail("Отправьте { enabled } или { is_default: true }.", 422);
    const result = await patchAiModel(id, body.data);
    return "model" in result ? NextResponse.json<AiModel>(result.model) : detail(result.error, result.status);
  },
};
