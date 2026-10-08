import { JsonResponse } from "@/mocks/runtime";

import type { HubSignal, SignalResponse } from "../domain/contract";
import { demoNow } from "./clock";
import { e, type IdCtx, notFound, withBackend } from "./respond";
import { openThreadsOf, summaryOf } from "./rules";
import { evidenceOf } from "./sessions";
import { demo, findHub } from "./store";

const DAY_MS = 86_400_000;
const CIRCLES = 3;

/** Quiet hours (22:00–08:00): the signal waits for the morning instead of being dropped. */
const quiet = (now: Date) => now.getUTCHours() >= 22 || now.getUTCHours() < 8;

function signalOf(hubId: string, now: Date): HubSignal | null {
  const hub = findHub(hubId);
  if (!hub || hub.archived) return null;
  const circling = openThreadsOf(hubId)
    .filter((t) => t.circles >= CIRCLES && !(t.dismissal && Date.parse(t.dismissal.until) > now.getTime()))
    .sort((a, b) => b.circles - a.circles)[0];
  if (!circling) return null;
  const blockers = circling.transitions.flatMap((t) => {
    const said = t.blocker ? evidenceOf(t.blocker) : null;
    return said ? [said.quote] : [];
  });
  return { hub: { id: hub.id, name: hub.name }, thread: summaryOf(circling, now), blockers };
}

/** POST /api/hubs/[id]/signal: the day's signal, if any; delivering it once keeps it from repeating. */
export const signalRoute = {
  POST: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    return withBackend(request, `/hubs/${e(id)}/signal`, () => {
      if (!findHub(id)) return notFound();
      const now = demoNow();
      const last = demo.signals.get(id);
      if (quiet(now) || (last && now.getTime() - Date.parse(last) < DAY_MS))
        return JsonResponse.json<SignalResponse>({ signal: null });
      const signal = signalOf(id, now);
      if (signal) demo.signals.set(id, now.toISOString());
      return JsonResponse.json<SignalResponse>({ signal });
    });
  },
};
