import { z } from "zod";

import { JsonResponse } from "@/mocks/runtime";

import { type ModelsResponse, STUDIO_ROLES } from "../domain/contract";
import { listModels, updateRole } from "./demo-models";
import { isProblem, refuse } from "./problems";
import { readJson } from "./prompt-schemas";

const roleBodySchema = z.object({
  model_id: z.string().max(200).nullable(),
  temperature: z.number().min(0).max(2),
  max_tokens: z.number().int().positive(),
  reasoning: z.boolean(),
});

/** /api/studio/models */
export const modelsRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<ModelsResponse>(listModels());
  },
};

/** /api/studio/models/roles/[role] */
export const roleModelRoute = {
  /** Saves which model fills a role and how it is called. */
  async PUT(request: Request, { params }: { params: Promise<{ role: string }> }) {
    const { role } = await params;
    const parsedRole = z.enum(STUDIO_ROLES).safeParse(role);
    if (!parsedRole.success) return refuse({ code: "unknownRole" }, 404);
    const body = roleBodySchema.safeParse(await readJson(request));
    if (!body.success) return refuse({ code: "invalidRequest" }, 422);
    const result = updateRole(parsedRole.data, body.data);
    return isProblem(result) ? refuse(result, 422) : JsonResponse.json(result);
  },
};
