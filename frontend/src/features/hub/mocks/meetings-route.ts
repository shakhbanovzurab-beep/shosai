import { JsonResponse } from "@/mocks/runtime";

import type { MeetingHub, MeetingPrep, PrepResponse } from "../domain/contract";
import { demoNow } from "./clock";
import { e, fail, half, type IdCtx, loaded, notFound, type SessionCtx, withBackend } from "./respond";
import { seriesOf } from "./sessions";
import { demo, findHub } from "./store";
import { briefOf, meetingHubOf, prepOf, sessionKnown, upcomingPreps } from "./views";

/** GET /api/meetings/[id]/hub: the meeting's hub, or a suggestion with its reason; never a silent filing. */
export const meetingHubRoute = {
  GET: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    return withBackend(request, `/meetings/${e(id)}/hub`, () => JsonResponse.json<MeetingHub>(meetingHubOf(id)));
  },
};

/**
 * /api/hubs/[id]/meetings/[sessionId]: a person files the meeting here (POST) or takes it out
 * (DELETE). A person's word is stronger than the machine's: the choice is remembered for the whole
 * calendar series, so its next meetings land here on their own.
 */
export const hubMeetingRoute = {
  POST: async (request: Request, { params }: SessionCtx) => {
    const { id, sessionId } = await params;
    return withBackend(request, `/hubs/${e(id)}/meetings/${e(sessionId)}`, () => {
      const hub = findHub(id);
      if (!hub || !sessionKnown(sessionId)) return notFound();
      if (hub.archived) return fail("hub_archived", 409);
      demo.filings.set(sessionId, { hubId: id, signal: "human" });
      demo.series.set(seriesOf(sessionId), id);
      return JsonResponse.json<MeetingHub>(meetingHubOf(sessionId));
    });
  },

  DELETE: async (request: Request, { params }: SessionCtx) => {
    const { id, sessionId } = await params;
    return withBackend(request, `/hubs/${e(id)}/meetings/${e(sessionId)}`, () => {
      if (!findHub(id)) return notFound();
      if (demo.filings.get(sessionId)?.hubId === id) demo.filings.delete(sessionId);
      if (demo.series.get(seriesOf(sessionId)) === id) demo.series.delete(seriesOf(sessionId));
      return JsonResponse.json<MeetingHub>(meetingHubOf(sessionId));
    });
  },
};

/** GET /api/meetings/[id]/prep: preparing for one upcoming meeting; null when there is nothing to say. */
export const meetingPrepRoute = {
  GET: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    return withBackend(request, `/meetings/${e(id)}/prep`, () => {
      const event = demo.events.find((ev) => ev.id === id);
      return JsonResponse.json<MeetingPrep | null>(event ? prepOf(event, demoNow()) : null);
    });
  },
};

/** GET /api/meetings/prep: every upcoming meeting this week whose hub is known, in one request. */
export const preparationsRoute = {
  GET: (request: Request) =>
    withBackend(request, "/meetings/prep", () => JsonResponse.json<PrepResponse>({ preps: upcomingPreps(demoNow()) })),
};

/** GET /api/brief/today: only what is really on fire across hubs; empty is a valid answer. */
export const briefRoute = {
  GET: (request: Request) =>
    withBackend(request, "/brief/today", () =>
      loaded(request, briefOf(demoNow()), (brief) => ({ ...brief, items: half(brief.items) })),
    ),
};
