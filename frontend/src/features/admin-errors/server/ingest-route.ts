import { NextResponse } from "next/server";

import { detail, forwardToBackend } from "@/server/backend-proxy";

import type { IngestEventResponse } from "../domain/ingest";
import { ingestEventSchema } from "../domain/schemas";
import { ingestEvent } from "./ingest";

/**
 * Called by the desktop clients (and platform services) for every captured error; see
 * `IngestEventRequest` in `../domain/ingest.ts`. The real backend authenticates the
 * client's ingest key; the demo accepts any caller.
 */
export const ingestRoute = {
  async POST(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/admin/errors/ingest");
    if (upstream) return upstream;
    const body = ingestEventSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) {
      const issue = body.error.issues[0];
      return detail(issue ? `${issue.path.join(".") || "body"}: ${issue.message}` : "Некорректное событие.", 422);
    }
    return NextResponse.json<IngestEventResponse>(ingestEvent(body.data), { status: 202 });
  },
};
