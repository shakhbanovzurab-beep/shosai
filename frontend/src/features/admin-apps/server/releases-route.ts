import { NextResponse } from "next/server";

import { z } from "zod";

import { detail, forwardToBackend } from "@/server/backend-proxy";

import { type AppRelease, RELEASE_MAX_BYTES, type ReleasesResponse } from "../domain/contract";
import { createRelease, deleteRelease, downloadRelease, listReleases, updateRelease } from "./demo-store";
import { ReleaseError } from "./multipart";

/* Route handlers for /api/admin/apps/releases/*: the backend when configured, the demo store otherwise. */

type Context = { params: Promise<{ id: string }> };

const PATH = "/v1/admin/apps/releases";
const releasePath = (id: string) => `${PATH}/${encodeURIComponent(id)}`;

const patchSchema = z
  .object({
    status: z.enum(["published", "revoked"]).optional(),
    rollout_percent: z.number().int().min(0).max(100).optional(),
  })
  .refine((patch) => patch.status !== undefined || patch.rollout_percent !== undefined);

/** A ReleaseError answers with its message and status; anything else is a real failure. */
function failure(error: unknown) {
  if (error instanceof ReleaseError) return detail(error.message, error.status);
  throw error;
}

/** /api/admin/apps/releases */
export const appReleasesRoute = {
  async GET(request: Request) {
    const upstream = await forwardToBackend(request, PATH);
    if (upstream) return upstream;
    return NextResponse.json<ReleasesResponse>({ releases: listReleases(), max_upload_bytes: RELEASE_MAX_BYTES });
  },

  /**
   * multipart/form-data: a `metadata` part (JSON ReleaseMetadata) first, then the build in `file`.
   * The body is streamed through to the backend, or to a temp file in the demo — never buffered whole.
   */
  async POST(request: Request) {
    const upstream = await forwardToBackend(request, PATH);
    if (upstream) return upstream;
    try {
      return NextResponse.json<AppRelease>(await createRelease(request), { status: 201 });
    } catch (error) {
      return failure(error);
    }
  },
};

/** /api/admin/apps/releases/[id] */
export const appReleaseRoute = {
  async PATCH(request: Request, { params }: Context) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, releasePath(id));
    if (upstream) return upstream;
    const body = patchSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return detail("Отправьте { status } или { rollout_percent } (целое от 0 до 100).", 422);
    try {
      return NextResponse.json<AppRelease>(updateRelease(id, body.data));
    } catch (error) {
      return failure(error);
    }
  },

  /** Drafts only. */
  async DELETE(request: Request, { params }: Context) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, releasePath(id));
    if (upstream) return upstream;
    try {
      await deleteRelease(id);
      return new Response(null, { status: 204 });
    } catch (error) {
      return failure(error);
    }
  },
};

/** /api/admin/apps/releases/[id]/download: the build as application/octet-stream, streamed from disk in the demo. */
export const appReleaseDownloadRoute = {
  async GET(request: Request, { params }: Context) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, `${releasePath(id)}/download`);
    if (upstream) return upstream;
    try {
      return await downloadRelease(id);
    } catch (error) {
      return failure(error);
    }
  },
};
