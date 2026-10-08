import { adoptFile, withdrawFile } from "@/features/workspace/mocks/sharing";
import { JsonResponse } from "@/mocks/runtime";

import {
  type FileItem,
  type FilesResponse,
  MAX_FILES_PER_UPLOAD,
  MAX_UPLOAD_BYTES,
  type UploadResponse,
} from "../domain/contract";
import { findFile, present, store } from "./demo-store";
import { addFiles, copyFile, reindexFile, updateFile } from "./file-ops";
import { copyWording, isProblem, refuse } from "./problems";
import { fileUpdateSchema, firstIssue, readJson, transferSchema } from "./schemas";

type Ctx = { params: Promise<{ id: string }> };

const gone = () => refuse({ code: "fileGone" }, 404);

/** /api/files */
export const filesRoute = {
  async GET(_request: Request) {
    const now = Date.now();
    return JsonResponse.json<FilesResponse>({
      folders: store.folders,
      files: store.files.map((f) => present(f, now)).toSorted((a, b) => b.modified_at.localeCompare(a.modified_at)),
    });
  },

  /** multipart/form-data: one or more `files`, optional `folder_id`, and `leo` = "true" to have Leo use them. */
  async POST(request: Request) {
    const form = await request.formData().catch(() => null);
    const files = form?.getAll("files").filter((part): part is File => part instanceof File) ?? [];
    if (files.length === 0) return refuse({ code: "chooseFile" }, 422);
    if (files.length > MAX_FILES_PER_UPLOAD) return refuse({ code: "tooManyFiles", max: MAX_FILES_PER_UPLOAD }, 422);
    const tooBig = files.find((f) => f.size > MAX_UPLOAD_BYTES);
    if (tooBig) return refuse({ code: "tooLarge", name: tooBig.name, bytes: MAX_UPLOAD_BYTES }, 413);
    const folder = form?.get("folder_id");
    const result = addFiles(files, typeof folder === "string" && folder ? folder : null, form?.get("leo") === "true");
    if (isProblem(result)) return refuse(result, 409);
    return JsonResponse.json<UploadResponse>({ files: result }, { status: 201 });
  },
};

/** /api/files/[id] */
export const fileRoute = {
  async PATCH(request: Request, { params }: Ctx) {
    const { id } = await params;
    const body = fileUpdateSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error), 422);
    const result = updateFile(id, body.data);
    if (result === null) return gone();
    return isProblem(result) ? refuse(result, 409) : JsonResponse.json<FileItem>(result);
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

/** /api/files/[id]/copy */
export const fileCopyRoute = {
  async POST(_request: Request, { params }: Ctx) {
    const { id } = await params;
    const copy = copyFile(id, await copyWording());
    return copy ? JsonResponse.json<FileItem>(copy, { status: 201 }) : gone();
  },
};

/** /api/files/[id]/reindex */
export const fileReindexRoute = {
  async POST(_request: Request, { params }: Ctx) {
    const { id } = await params;
    const result = reindexFile(id);
    if (result === null) return gone();
    return isProblem(result) ? refuse(result, 409) : JsonResponse.json<FileItem>(result);
  },
};

/** /api/files/[id]/transfer: the workspace takes over a file shared there; it leaves My files. */
export const fileTransferRoute = {
  async POST(request: Request, { params }: Ctx) {
    const { id } = await params;
    const body = transferSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error), 422);
    if (!findFile(id)) return gone();
    if (!adoptFile(body.data.workspace_id, id)) return refuse({ code: "shareFirst" }, 409);
    store.files = store.files.filter((f) => f.id !== id);
    // It no longer exists here, so other workspaces it was shared in lose it.
    withdrawFile(id);
    return new Response(null, { status: 204 });
  },
};
