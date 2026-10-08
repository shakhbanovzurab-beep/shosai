import { z } from "zod";

import { detail, JsonResponse } from "@/mocks/runtime";

import { type AppRelease, RELEASE_MAX_BYTES, type ReleasesResponse } from "../domain/contract";
import { createRelease, deleteRelease, downloadRelease, listReleases, updateRelease } from "./demo-store";
import { ReleaseError } from "./release-error";

/* Route handlers for /api/admin/apps/releases/*: the backend when configured, the demo store otherwise. */

type Context = { params: Promise<{ id: string }> };

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
  async GET(_request: Request) {
    return JsonResponse.json<ReleasesResponse>({ releases: listReleases(), max_upload_bytes: RELEASE_MAX_BYTES });
  },

  /**
   * multipart/form-data: a `metadata` part (JSON ReleaseMetadata) first, then the build in `file`.
   * The body is streamed through to the backend, or to a temp file in the demo — never buffered whole.
   */
  async POST(request: Request) {
    try {
      return JsonResponse.json<AppRelease>(await createRelease(request), { status: 201 });
    } catch (error) {
      return failure(error);
    }
  },
};

/** /api/admin/apps/releases/[id] */
export const appReleaseRoute = {
  async PATCH(request: Request, { params }: Context) {
    const { id } = await params;
    const body = patchSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return detail("Отправьте { status } или { rollout_percent } (целое от 0 до 100).", 422);
    try {
      return JsonResponse.json<AppRelease>(updateRelease(id, body.data));
    } catch (error) {
      return failure(error);
    }
  },

  /** Drafts only. */
  async DELETE(_request: Request, { params }: Context) {
    const { id } = await params;
    try {
      deleteRelease(id);
      return new Response(null, { status: 204 });
    } catch (error) {
      return failure(error);
    }
  },
};

/** /api/admin/apps/releases/[id]/download: the build as application/octet-stream, streamed from disk in the demo. */
export const appReleaseDownloadRoute = {
  async GET(_request: Request, { params }: Context) {
    const { id } = await params;
    try {
      return downloadRelease(id);
    } catch (error) {
      return failure(error);
    }
  },
};
