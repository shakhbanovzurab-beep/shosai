import { NextResponse } from "next/server";

import { z } from "zod";

import { DISMISS_DAYS, type ThreadDetail, type ThreadStage, type ThreadSummary } from "../domain/contract";
import { isOpenStage } from "../domain/urgency";
import { addDays, demoNow } from "./clock";
import { e, fail, half, type IdCtx, loaded, notFound, readJson, withBackend } from "./respond";
import { gapOf, openThreadsOf, summaryOf } from "./rules";
import { findHub, findThread } from "./store";
import type { StoredThread } from "./types";
import { detailOf } from "./views";

const dismissSchema = z.object({
  gapKind: z.enum([
    "contradiction",
    "overdue",
    "due_soon",
    "forgotten",
    "undated",
    "orphan_decision",
    "unanswered",
    "silence",
  ]),
});
const assignSchema = z.object({ owner: z.string().trim().min(1).max(80) });

const summaryJson = (thread: StoredThread) => NextResponse.json<ThreadSummary>(summaryOf(thread, demoNow()));

/** /api/hubs/[id]/threads?state=open: every row of "What's unresolved" in one request. */
export const hubThreadsRoute = {
  GET: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    return withBackend(request, `/hubs/${e(id)}/threads?state=open`, () => {
      if (!findHub(id)) return notFound();
      const now = demoNow();
      return loaded(
        request,
        openThreadsOf(id).map((t) => summaryOf(t, now)),
        half,
      );
    });
  },
};

/** /api/threads/[id]: the topic with its history, sources and links. */
export const threadRoute = {
  GET: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    return withBackend(request, `/threads/${e(id)}`, () => {
      const thread = findThread(id);
      return thread ? NextResponse.json<ThreadDetail>(detailOf(thread, demoNow())) : notFound();
    });
  },
};

/** Closes the topic as done or abandoned, remembering how it was so the toast's Undo can put it back. */
const closeAs = (stage: ThreadStage, path: string) => ({
  POST: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    return withBackend(request, `/threads/${e(id)}/${path}`, () => {
      const thread = findThread(id);
      if (!thread) return notFound();
      if (findHub(thread.hubId)?.archived) return fail("hub_archived", 409);
      if (isOpenStage(thread.stage)) {
        thread.undo = { stage: thread.stage, dismissal: thread.dismissal };
        thread.stage = stage;
        thread.transitions.push({
          from: thread.undo.stage,
          to: stage,
          said: null,
          at: demoNow().toISOString(),
          by: "human",
          blocker: null,
        });
      }
      return summaryJson(thread);
    });
  },
  DELETE: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    return withBackend(request, `/threads/${e(id)}/${path}`, () => {
      const thread = findThread(id);
      if (!thread) return notFound();
      if (thread.stage === stage && thread.undo) {
        thread.stage = thread.undo.stage;
        thread.transitions.pop();
        thread.undo = null;
      }
      return summaryJson(thread);
    });
  },
});

/** POST /api/threads/[id]/done ("Done"); DELETE undoes it. */
export const doneRoute = closeAs("closed", "done");

/** POST /api/threads/[id]/abandon (closed without being done); DELETE undoes it. */
export const abandonRoute = closeAs("abandoned", "abandon");

/** POST /api/threads/[id]/dismiss ("Not the case"): the gap is off for 90 days, everywhere. DELETE undoes it. */
export const dismissRoute = {
  POST: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    return withBackend(request, `/threads/${e(id)}/dismiss`, async () => {
      const thread = findThread(id);
      if (!thread) return notFound();
      const body = dismissSchema.safeParse(await readJson(request));
      if (!body.success) return fail("invalid", 422);
      const now = demoNow();
      if (gapOf(thread, now)?.kind === body.data.gapKind) {
        thread.undo = { stage: thread.stage, dismissal: thread.dismissal };
        thread.dismissal = {
          gapKind: body.data.gapKind,
          at: now.toISOString(),
          until: addDays(now, DISMISS_DAYS).toISOString(),
          by: "human",
          evidence: "",
        };
      }
      return summaryJson(thread);
    });
  },
  DELETE: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    return withBackend(request, `/threads/${e(id)}/dismiss`, () => {
      const thread = findThread(id);
      if (!thread) return notFound();
      if (thread.undo) {
        thread.dismissal = thread.undo.dismissal;
        thread.undo = null;
      }
      return summaryJson(thread);
    });
  },
};

/** POST /api/threads/[id]/assign: someone takes it. */
export const assignRoute = {
  POST: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    return withBackend(request, `/threads/${e(id)}/assign`, async () => {
      const thread = findThread(id);
      if (!thread) return notFound();
      const body = assignSchema.safeParse(await readJson(request));
      if (!body.success) return fail("invalid", 422);
      thread.owner = body.data.owner;
      return summaryJson(thread);
    });
  },
};
