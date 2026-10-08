import { JsonResponse } from "@/mocks/runtime";

import type { StudioContext } from "../domain/contract";
import { getContext, saveContext } from "./demo-context";
import { refuse } from "./problems";
import { contextBodySchema, firstIssue, readJson } from "./prompt-schemas";

/** /api/studio/context */
export const contextRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<StudioContext>(getContext());
  },

  async PUT(request: Request) {
    const body = contextBodySchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error), 422);
    return JsonResponse.json<StudioContext>(saveContext(body.data.content.trim()));
  },
};
