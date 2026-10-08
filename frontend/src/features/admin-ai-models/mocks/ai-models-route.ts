import { detail, JsonResponse } from "@/mocks/runtime";

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
  async GET(_request: Request) {
    return JsonResponse.json<AiModelsResponse>(await getAiModels());
  },
};

/** `/api/admin/ai-models/check`: reaches OpenRouter with the server's key. */
export const aiModelsCheckRoute = {
  async POST(_request: Request) {
    return JsonResponse.json<ConnectionCheckResponse>(await checkConnection());
  },
};

/** `/api/admin/ai-models/{id}`: switches a model on or off, or makes it the default. */
export const aiModelRoute = {
  async PATCH(request: Request, { params }: Context) {
    const { id } = await params;
    const body = aiModelPatchSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return detail("Отправьте { enabled } или { is_default: true }.", 422);
    const result = await patchAiModel(id, body.data);
    return "model" in result ? JsonResponse.json<AiModel>(result.model) : detail(result.error, result.status);
  },
};
