import { NextResponse } from "next/server";

import { forwardToBackend } from "@/server/backend-proxy";

import type { CannedRepliesResponse } from "../domain/contract";
import { listCannedReplies } from "./support-demo";

/** `/api/admin/support/canned-replies`: the team's saved answers. */
export const cannedRepliesRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/admin/support/canned-replies");
    if (upstream) return upstream;
    return NextResponse.json<CannedRepliesResponse>({ replies: listCannedReplies() });
  },
};
