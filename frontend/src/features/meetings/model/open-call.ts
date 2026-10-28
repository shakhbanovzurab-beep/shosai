import { MOCK_API } from "@/config/unserved-slices";
import { ApiError } from "@/lib/api/errors";

import type { CallSession, CallSetup } from "../domain/call-session";

/**
 * Открыть звонок после лобби. На моках разработки — демо-звонок; к LiveKit кабинет подключается шагом A10, а до
 * него звонок недоступен так же, как при недоступном сервере видео.
 */
export async function openCall(setup: CallSetup): Promise<CallSession> {
  if (MOCK_API) {
    const { DemoCall } = await import("../data/demo-call");
    return new DemoCall(setup);
  }
  throw new ApiError("video_unavailable", 503, "video_unavailable");
}
