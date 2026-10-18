import { effectiveEntitlements } from "@/features/upgrade/mocks/demo-plans";
import { withdrawFile } from "@/features/workspace/mocks/sharing";
import { JsonResponse } from "@/mocks/runtime";

import type { FileItem, FilesResponse, UploadResponse } from "../domain/contract";
import { findFile, leoBytes, present, store, usedBytes } from "./demo-store";
import { addFiles, copyFile, reindexFile, updateFile } from "./file-ops";
import { isProblem, problem, refuse } from "./problems";
import { fileUpdateSchema, firstIssue, readJson, registerSchema } from "./schemas";

type Ctx = { params: Promise<{ id: string }> };

const gone = () => refuse(problem("file_not_found", 404));
const LINK_MS = 15 * 60_000;

/** /v1/files */
export const filesRoute = {
  async GET(_request: Request) {
    const now = Date.now();
    return JsonResponse.json<FilesResponse>({
      folders: store.folders,
      files: store.files.map((f) => present(f, now)).toSorted((a, b) => b.modified_at.localeCompare(a.modified_at)),
    });
  },

  /** Ready uploads become files: `{ upload_ids, folder_id?, leo? }`. */
  async POST(request: Request) {
    const body = registerSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error));
    const result = addFiles(body.data.upload_ids, body.data.folder_id ?? null, body.data.leo ?? false);
    if (isProblem(result)) return refuse(result);
    return JsonResponse.json<UploadResponse>({ files: result }, { status: 201 });
  },
};

/** /v1/files/storage: the stored bytes and Leo's bytes against the demo plan; never over a limit for long. */
export const storageRoute = {
  async GET(_request: Request) {
    const plan = effectiveEntitlements();
    const gb = plan?.file_manager_gb;
    const mb = plan?.knowledge_base_mb;
    return JsonResponse.json({
      used_bytes: usedBytes(),
      limit_bytes: gb === null || gb === undefined ? null : gb * 1024 ** 3,
      over_limit_since: null,
      removal_at: null,
      leo_used_bytes: leoBytes(store),
      leo_limit_bytes: mb === null || mb === undefined ? null : mb * 1024 ** 2,
      leo_over_limit_since: null,
      leo_removal_at: null,
    });
  },
};

/** /v1/files/[id] */
export const fileRoute = {
  async PATCH(request: Request, { params }: Ctx) {
    const { id } = await params;
    const body = fileUpdateSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error));
    const result = updateFile(id, body.data);
    if (result === null) return gone();
    return isProblem(result) ? refuse(result) : JsonResponse.json<FileItem>(result);
  },

  async DELETE(_request: Request, { params }: Ctx) {
    const { id } = await params;
    if (!findFile(id)) return gone();
    store.files = store.files.filter((f) => f.id !== id);
    // Workspaces only point to it, so it leaves them too.
    withdrawFile(id);
    return new Response(null, { status: 204 });
  },
};

/** /v1/files/[id]/copy */
export const fileCopyRoute = {
  async POST(_request: Request, { params }: Ctx) {
    const copy = copyFile((await params).id);
    return copy ? JsonResponse.json<FileItem>(copy, { status: 201 }) : gone();
  },
};

/** /v1/files/[id]/reindex */
export const fileReindexRoute = {
  async POST(_request: Request, { params }: Ctx) {
    const result = reindexFile((await params).id);
    if (result === null) return gone();
    return isProblem(result) ? refuse(result) : JsonResponse.json<FileItem>(result);
  },
};

/** /v1/files/[id]/download: a link on this origin, as the edge's `/dl/…` would be. */
export const fileDownloadRoute = {
  async GET(_request: Request, { params }: Ctx) {
    const { id } = await params;
    if (!findFile(id)) return gone();
    const expires_at = new Date(Date.now() + LINK_MS).toISOString();
    return JsonResponse.json({ url: `/demo-files/${encodeURIComponent(id)}`, expires_at });
  },
};

/** /demo-files/[id]: the demo has no bytes, so a download is a short text saying so. */
export const demoFileBytesRoute = {
  async GET(_request: Request, { params }: Ctx) {
    const file = findFile((await params).id);
    if (!file) return new Response(null, { status: 404 });
    return new Response(`Demo file: ${file.name}\n`, {
      headers: { "content-type": "text/plain; charset=utf-8", "content-disposition": "attachment" },
    });
  },
};
