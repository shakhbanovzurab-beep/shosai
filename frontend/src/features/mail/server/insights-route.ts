import { NextResponse } from "next/server";

import { forwardToBackend } from "@/server/backend-proxy";

import type { MailInsightsResponse } from "../domain/leo-insights";
import { listInsights } from "./demo-insights";

/**
 * /api/mail/insights. Leo's summaries, next steps and drafts are written by the model, never looked up in
 * the catalogs: the backend gets the interface language as `Accept-Language` (forwardToBackend) and writes
 * them in it. The demo's readings are fixed English fixtures.
 */
export const insightsRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/mail/insights");
    if (upstream) return upstream;
    return NextResponse.json<MailInsightsResponse>({ insights: listInsights() });
  },
};
