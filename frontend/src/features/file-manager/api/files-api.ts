import { apiRequest, jsonBody } from "@/lib/api-client";

import type { FileFolder, FileItem, FilesResponse, FileUpdate, FolderUpdate, UploadResponse } from "../domain/contract";

const file = (id: string, rest = "") => `/api/files/${encodeURIComponent(id)}${rest}`;
const folder = (id: string) => `/api/files/folders/${encodeURIComponent(id)}`;

export const filesApi = {
  list: () => apiRequest<FilesResponse>("/api/files"),
  upload: (files: File[], options: { folderId: string | null; leo: boolean }) => {
    const form = new FormData();
    for (const part of files) form.append("files", part);
    if (options.folderId) form.append("folder_id", options.folderId);
    if (options.leo) form.append("leo", "true");
    return apiRequest<UploadResponse>("/api/files", { method: "POST", body: form });
  },
  update: (id: string, patch: FileUpdate) => apiRequest<FileItem>(file(id), jsonBody("PATCH", patch)),
  remove: (id: string) => apiRequest<void>(file(id), { method: "DELETE" }),
  copy: (id: string) => apiRequest<FileItem>(file(id, "/copy"), { method: "POST" }),
  reindex: (id: string) => apiRequest<FileItem>(file(id, "/reindex"), { method: "POST" }),
  transfer: (id: string, workspaceId: string) =>
    apiRequest<void>(file(id, "/transfer"), jsonBody("POST", { workspace_id: workspaceId })),

  createFolder: (name: string) => apiRequest<FileFolder>("/api/files/folders", jsonBody("POST", { name })),
  updateFolder: (id: string, patch: FolderUpdate) => apiRequest<FileFolder>(folder(id), jsonBody("PATCH", patch)),
  removeFolder: (id: string) => apiRequest<void>(folder(id), { method: "DELETE" }),
};
