import { MOCK_API } from "@/config/unserved-slices";
import { ApiError } from "@/lib/api/errors";

import type { CallSession, CallSetup } from "../domain/call-session";

/** Открыть звонок после лобби: на моках разработки — демо-звонок, иначе — LiveKit; не подключился — недоступен. */
export async function openCall(setup: CallSetup): Promise<CallSession> {
  if (MOCK_API) {
    const { DemoCall } = await import("../data/demo-call");
    return new DemoCall(setup);
  }
  // livekit-client — отдельным чанком только страницы комнаты.
  const { LiveKitCall } = await import("./livekit-call");
  const call = new LiveKitCall(setup);
  try {
    await call.connect();
  } catch {
    call.leave();
    throw new ApiError("video_unavailable", 503, "video_unavailable");
  }
  return call;
}
