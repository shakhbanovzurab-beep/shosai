import { JsonResponse } from "@/mocks/runtime";

import type { MailInsightsResponse } from "../domain/leo-insights";
import { listInsights } from "./demo-insights";

/**
 * /api/mail/insights. Leo's summaries, next steps and drafts are written by the model, never looked up in
 * the catalogs: the backend gets the interface language as `Accept-Language` (forwardToBackend) and writes
 * them in it. The demo's readings are fixed English fixtures.
 */
export const insightsRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<MailInsightsResponse>({ insights: listInsights() });
  },
};
