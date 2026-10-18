import { effectiveEntitlements } from "@/features/upgrade/mocks/demo-plans";
import type { components } from "@/lib/api/generated/schema";
import { JsonResponse } from "@/mocks/runtime";

import { MAX_UPLOAD_BYTES } from "../domain/contract";
import { usedBytes } from "./demo-store";
import { type Problem, problem, refuse } from "./problems";
import { firstIssue, readJson, uploadSchema } from "./schemas";

/*
 * Uploads in the demo, as the backend runs them (FL-D1): parts signed for exact lengths, PUT to a stand-in
 * bucket on this origin, assembled on completion. Nothing is kept but the sizes.
 */

type UploadAnswer = components["schemas"]["UploadAnswer"];
type DemoUpload = Omit<UploadAnswer, "parts" | "done_parts"> & { partSizes: number[]; received: Map<number, number> };

const PART_BYTES = 16 * 1024 * 1024;
const LINK_MS = 15 * 60_000;
const shared = globalThis as typeof globalThis & { fileUploadsDemo?: Map<string, DemoUpload> };
shared.fileUploadsDemo ??= new Map();
const uploads = shared.fileUploadsDemo;

const partSizes = (size: number) =>
  Array.from({ length: Math.ceil(size / PART_BYTES) }, (_, i) => Math.min(PART_BYTES, size - i * PART_BYTES));

function answer(upload: DemoUpload): UploadAnswer {
  const { partSizes: sizes, received, ...rest } = upload;
  const expires_at = new Date(Date.now() + LINK_MS).toISOString();
  const parts = sizes
    .map((size_bytes, index) => ({ number: index + 1, size_bytes }))
    .filter(({ number }) => !received.has(number))
    .map((part) => ({ ...part, url: `/demo-bucket/${upload.id}/${part.number}`, headers: {}, expires_at }));
  return { ...rest, done_parts: [...received.keys()].toSorted((a, b) => a - b), parts };
}

/** The plan's storage refuses the bytes: not included at all, or over the limit with what's stored. */
function storageRefusal(size: number): Problem | null {
  const gb = effectiveEntitlements()?.file_manager_gb;
  if (gb === null || gb === undefined) return null;
  if (gb === 0) return problem("storage_not_included", 403);
  return usedBytes() + size > gb * 1024 ** 3 ? problem("storage_limit", 413) : null;
}

/** Gives back an upload a refused registration claimed. */
export function unclaimUpload(id: string) {
  const upload = uploads.get(id);
  if (upload?.state === "claimed") upload.state = "ready";
}

/** A ready upload the File Manager may take, once; the problem otherwise. */
export function claimUpload(id: string): DemoUpload | Problem {
  const upload = uploads.get(id);
  if (upload?.state !== "ready") return problem("upload_not_claimable", 409);
  upload.state = "claimed";
  return upload;
}

type Ctx = { params: Promise<{ id: string }> };
type PartCtx = { params: Promise<{ id: string; part: string }> };

const missing = () => refuse(problem("upload_not_found", 404));

/** /v1/me/uploads */
export const uploadsRoute = {
  async POST(request: Request) {
    const body = uploadSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error));
    if (body.data.size_bytes > MAX_UPLOAD_BYTES) return refuse(problem("upload_too_large", 413));
    const refused = storageRefusal(body.data.size_bytes);
    if (refused) return refuse(refused);
    const { filename, content_type, size_bytes } = body.data;
    const upload: DemoUpload = {
      id: crypto.randomUUID(),
      purpose: "file_manager",
      state: "pending",
      filename,
      content_type: content_type || "application/octet-stream",
      size_bytes,
      expires_at: new Date(Date.now() + 86_400_000).toISOString(),
      partSizes: partSizes(size_bytes),
      received: new Map(),
    };
    uploads.set(upload.id, upload);
    return JsonResponse.json(answer(upload), { status: 201 });
  },
};

/** /v1/me/uploads/[id] */
export const uploadRoute = {
  async GET(_request: Request, { params }: Ctx) {
    const upload = uploads.get((await params).id);
    return upload ? JsonResponse.json(answer(upload)) : missing();
  },
  async DELETE(_request: Request, { params }: Ctx) {
    uploads.delete((await params).id);
    return new Response(null, { status: 204 });
  },
};

/** /v1/me/uploads/[id]/complete */
export const uploadCompleteRoute = {
  async POST(_request: Request, { params }: Ctx) {
    const upload = uploads.get((await params).id);
    if (!upload) return missing();
    if (upload.received.size < upload.partSizes.length) return refuse(problem("upload_incomplete", 409));
    const total = [...upload.received.values()].reduce((sum, bytes) => sum + bytes, 0);
    if (upload.state === "pending") upload.state = total === upload.size_bytes ? "ready" : "rejected";
    return JsonResponse.json(answer(upload));
  },
};

/** /demo-bucket/[id]/[part]: the stand-in bucket takes a part and keeps only its size. */
export const demoBucketRoute = {
  async PUT(request: Request, { params }: PartCtx) {
    const { id, part } = await params;
    const upload = uploads.get(id);
    if (!upload) return new Response(null, { status: 404 });
    upload.received.set(Number(part), (await request.arrayBuffer()).byteLength);
    return new Response(null, { status: 200 });
  },
};
