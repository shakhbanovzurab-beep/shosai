import { NextResponse } from "next/server";

import { z } from "zod";

import type { Material } from "../domain/contract";
import { demoNow } from "./clock";
import { e, fail, half, type IdCtx, loaded, type MaterialCtx, notFound, readJson, withBackend } from "./respond";
import { demo, findHub } from "./store";
import { digestOf, feedOf } from "./views";

const linkSchema = z.object({ title: z.string().trim().min(1).max(200), url: z.url().max(2000) });

/** /api/hubs/[id]/digest/[sessionId]: after a meeting ("latest" for the last one); null before any. */
export const digestRoute = {
  GET: async (request: Request, { params }: { params: Promise<{ id: string; sessionId: string }> }) => {
    const { id, sessionId } = await params;
    return withBackend(request, `/hubs/${e(id)}/digest/${e(sessionId)}`, () => {
      if (!findHub(id)) return notFound();
      return loaded(request, digestOf(id, sessionId, demoNow()), (digest) =>
        digest ? { ...digest, closed: [], opened: [] } : digest,
      );
    });
  },
};

/** /api/hubs/[id]/feed?cursor=: the hub's meetings and what was said in them, newest first, a page at a time. */
export const feedRoute = {
  GET: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    const cursor = new URL(request.url).searchParams.get("cursor");
    return withBackend(request, `/hubs/${e(id)}/feed${cursor ? `?cursor=${e(cursor)}` : ""}`, () => {
      if (!findHub(id)) return notFound();
      return loaded(request, feedOf(id, cursor), (page) => ({ ...page, meetings: half(page.meetings) }));
    });
  },
};

/** A file stored for the demo only by name: it opens nowhere, which the list shows plainly. */
function uploaded(file: File): Material {
  return {
    id: `mat-${crypto.randomUUID().slice(0, 8)}`,
    kind: "file",
    title: file.name.slice(0, 200),
    sessionId: null,
    url: null,
    addedAt: new Date().toISOString(),
    gone: false,
  };
}

/** /api/hubs/[id]/materials: documents and file links; adding a link or uploading a file. */
export const materialsRoute = {
  GET: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    return withBackend(request, `/hubs/${e(id)}/materials`, () => {
      if (!findHub(id)) return notFound();
      return loaded(request, demo.materials.get(id) ?? [], half);
    });
  },

  POST: async (request: Request, { params }: IdCtx) => {
    const { id } = await params;
    return withBackend(request, `/hubs/${e(id)}/materials`, async () => {
      if (!findHub(id)) return notFound();
      let material: Material;
      if (request.headers.get("content-type")?.startsWith("multipart/form-data")) {
        const file = (await request.formData().catch(() => null))?.get("file");
        if (!(file instanceof File)) return fail("invalid", 422);
        material = uploaded(file);
      } else {
        const body = linkSchema.safeParse(await readJson(request));
        if (!body.success) return fail("invalid", 422);
        const { title, url } = body.data;
        material = {
          id: `mat-${crypto.randomUUID().slice(0, 8)}`,
          kind: "file",
          title,
          sessionId: null,
          url,
          addedAt: new Date().toISOString(),
          gone: false,
        };
      }
      demo.materials.set(id, [material, ...(demo.materials.get(id) ?? [])]);
      return NextResponse.json<Material>(material, { status: 201 });
    });
  },
};

/** DELETE /api/hubs/[id]/materials/[materialId]: out of the hub; the document itself stays where it is. */
export const materialRoute = {
  DELETE: async (request: Request, { params }: MaterialCtx) => {
    const { id, materialId } = await params;
    return withBackend(request, `/hubs/${e(id)}/materials/${e(materialId)}`, () => {
      const list = demo.materials.get(id);
      if (!findHub(id) || !list?.some((m) => m.id === materialId)) return notFound();
      demo.materials.set(
        id,
        list.filter((m) => m.id !== materialId),
      );
      return new Response(null, { status: 204 });
    });
  },
};
