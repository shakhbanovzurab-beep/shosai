import { NextResponse } from "next/server";

import { z } from "zod";

import { CHARTER_MAX, HUB_NAME_MAX, HUB_NAME_MIN, type Hub, type HubsResponse } from "../domain/contract";
import { demoNow } from "./clock";
import { e, fail, type IdCtx, notFound, readJson, withBackend } from "./respond";
import { hubOf } from "./rules";
import { addHub, boardExists, deleteHub, demo, findHub, MAX_HUBS, nameTaken } from "./store";

const nameSchema = z.object({ name: z.string() });
const charterSchema = z.object({
  purpose: z.string().max(CHARTER_MAX).nullable(),
  success: z.string().max(CHARTER_MAX).nullable(),
});
const boardSchema = z.object({ boardId: z.string().min(1).max(64).nullable() });
const archivedSchema = z.object({ archived: z.boolean() });

/** A name a person wrote: trimmed, 2–200 characters, not taken by another hub. */
function checkName(raw: unknown, except: string | null) {
  const body = nameSchema.safeParse(raw);
  if (!body.success) return { error: fail("invalid", 422) };
  const name = body.data.name.trim().replace(/\s+/g, " ");
  if (name.length < HUB_NAME_MIN) return { error: fail("name_too_short", 422) };
  if (name.length > HUB_NAME_MAX) return { error: fail("name_too_long", 422) };
  if (nameTaken(name, except)) return { error: fail("name_taken", 409) };
  return { name };
}

const hubJson = (hub: NonNullable<ReturnType<typeof findHub>>, status = 200) =>
  NextResponse.json<Hub>(hubOf(hub, demoNow()), { status });

const blank = (value: string | null) => (value?.trim() ? value.trim() : null);

/** /api/hubs: the list with what each row needs (no request per row), and creating a hub. */
export const hubsRoute = {
  GET: (request: Request) => {
    const includeArchived = new URL(request.url).searchParams.get("include_archived") === "true";
    return withBackend(request, `/hubs?include_archived=${includeArchived}`, () => {
      const now = demoNow();
      const hubs = [...demo.hubs.values()]
        .filter((h) => includeArchived || !h.archived)
        .map((h) => hubOf(h, now))
        .sort((a, b) => (b.lastConversationAt ?? b.createdAt).localeCompare(a.lastConversationAt ?? a.createdAt));
      return NextResponse.json<HubsResponse>({ hubs });
    });
  },

  POST: (request: Request) =>
    withBackend(request, "/hubs", async () => {
      const checked = checkName(await readJson(request), null);
      if (checked.error) return checked.error;
      if (demo.hubs.size >= MAX_HUBS) return fail("too_many_hubs", 409);
      return hubJson(addHub(checked.name), 201);
    }),
};

/** /api/hubs/[id]: renaming and deleting. */
export const hubRoute = {
  PATCH: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    return withBackend(request, `/hubs/${e(id)}`, async () => {
      const hub = findHub(id);
      if (!hub) return notFound();
      const checked = checkName(await readJson(request), id);
      if (checked.error) return checked.error;
      hub.name = checked.name;
      return hubJson(hub);
    });
  },

  /** The hub and its addressing go; meetings, tasks and documents stay where they are. */
  DELETE: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    return withBackend(request, `/hubs/${e(id)}`, () => {
      if (!findHub(id)) return notFound();
      deleteHub(id);
      return new Response(null, { status: 204 });
    });
  },
};

/** PUT /api/hubs/[id]/charter: why the hub exists and what counts as success, in the person's words. */
export const charterRoute = {
  PUT: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    return withBackend(request, `/hubs/${e(id)}/charter`, async () => {
      const hub = findHub(id);
      if (!hub) return notFound();
      const body = charterSchema.safeParse(await readJson(request));
      if (!body.success) return fail("invalid", 422);
      hub.purpose = blank(body.data.purpose);
      hub.success = blank(body.data.success);
      return hubJson(hub);
    });
  },
};

/** PUT /api/hubs/[id]/board: where the work from its meetings goes; null for nowhere. */
export const boardRoute = {
  PUT: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    return withBackend(request, `/hubs/${e(id)}/board`, async () => {
      const hub = findHub(id);
      if (!hub) return notFound();
      const body = boardSchema.safeParse(await readJson(request));
      if (!body.success) return fail("invalid", 422);
      if (body.data.boardId !== null && !boardExists(body.data.boardId)) return fail("board_gone", 409);
      hub.boardId = body.data.boardId;
      return hubJson(hub);
    });
  },
};

/** PUT /api/hubs/[id]/archived: into the archive (the client asks first) and back (no questions). */
export const archivedRoute = {
  PUT: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    return withBackend(request, `/hubs/${e(id)}/archived`, async () => {
      const hub = findHub(id);
      if (!hub) return notFound();
      const body = archivedSchema.safeParse(await readJson(request));
      if (!body.success) return fail("invalid", 422);
      hub.archived = body.data.archived;
      return hubJson(hub);
    });
  },
};
