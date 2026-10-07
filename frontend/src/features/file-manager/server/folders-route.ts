import { NextResponse } from "next/server";

import { forwardToBackend } from "@/server/backend-proxy";

import type { FileFolder } from "../domain/contract";
import { createFolder, deleteFolder, updateFolder } from "./file-ops";
import { isProblem, refuse } from "./problems";
import { firstIssue, folderCreateSchema, folderUpdateSchema, readJson } from "./schemas";

type Ctx = { params: Promise<{ id: string }> };

const gone = () => refuse({ code: "folderGone" }, 404);
const path = (id: string) => `/v1/files/folders/${encodeURIComponent(id)}`;

/** /api/files/folders */
export const foldersRoute = {
  async POST(request: Request) {
    const upstream = await forwardToBackend(request, "/v1/files/folders");
    if (upstream) return upstream;
    const body = folderCreateSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error), 422);
    return NextResponse.json<FileFolder>(createFolder(body.data.name), { status: 201 });
  },
};

/** /api/files/folders/[id] */
export const folderRoute = {
  async PATCH(request: Request, { params }: Ctx) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, path(id));
    if (upstream) return upstream;
    const body = folderUpdateSchema.safeParse(await readJson(request));
    if (!body.success) return refuse(firstIssue(body.error), 422);
    const result = updateFolder(id, body.data);
    if (result === null) return gone();
    return isProblem(result) ? refuse(result, 409) : NextResponse.json<FileFolder>(result);
  },

  async DELETE(request: Request, { params }: Ctx) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, path(id));
    if (upstream) return upstream;
    return deleteFolder(id) ? new Response(null, { status: 204 }) : gone();
  },
};
