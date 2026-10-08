import { effectiveEntitlements } from "@/features/upgrade/mocks/demo-plans";
import { JsonResponse } from "@/mocks/runtime";

import type { IndexResponse, IndexSettings } from "../domain/contract";

/* In-memory stand-in for the index service, used when BACKEND_API_URL is unset. */

const DEMO_INDEX: IndexSettings = {
  embedding_model: "gemini-embedding-2",
  dimensions: 3072,
  chunk_size: 800,
  chunk_overlap: 120,
};

const MB = 1024 * 1024;

/** /api/knowledge-base/index: how Leo's index is built, and how much it may hold on the current plan. */
export const indexRoute = {
  async GET(_request: Request) {
    const limit = effectiveEntitlements()?.knowledge_base_mb;
    return JsonResponse.json<IndexResponse>({
      index: DEMO_INDEX,
      limit_bytes: limit === null || limit === undefined ? null : limit * MB,
    });
  },
};
