import { JsonResponse } from "@/mocks/runtime";

import type { CannedRepliesResponse } from "../domain/contract";
import { listCannedReplies } from "./support-demo";

/** `/api/admin/support/canned-replies`: the team's saved answers. */
export const cannedRepliesRoute = {
  async GET(_request: Request) {
    return JsonResponse.json<CannedRepliesResponse>({ replies: listCannedReplies() });
  },
};
