import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

import type {
  FileFolder,
  FileItem,
  FilesResponse,
  FileUpdate,
  FolderUpdate,
  StorageStanding,
  UploadResponse,
} from "../domain/contract";

export type DownloadLink = components["schemas"]["DownloadOut"];

const file = (id: string) => ({ params: { path: { file_id: id } } });
const folder = (id: string) => ({ params: { path: { folder_id: id } } });

/** The person's File Manager on `/v1/files*` (backend `files`, steps 4–6). */
export const filesApi = {
  list: (): Promise<FilesResponse> => dataOf(apiClient.GET("/v1/files")),
  /** Ready uploads become files, 1–20 at a time; a repeat answers the same files. */
  register: (uploadIds: string[], options: { folderId: string | null; leo: boolean }): Promise<UploadResponse> =>
    dataOf(
      apiClient.POST("/v1/files", {
        body: { upload_ids: uploadIds, folder_id: options.folderId, leo: options.leo },
      }),
    ),
  update: (id: string, patch: FileUpdate): Promise<FileItem> =>
    dataOf(apiClient.PATCH("/v1/files/{file_id}", { ...file(id), body: patch })),
  remove: (id: string): Promise<void> => dataOf(apiClient.DELETE("/v1/files/{file_id}", file(id))),
  copy: (id: string): Promise<FileItem> => dataOf(apiClient.POST("/v1/files/{file_id}/copy", file(id))),
  reindex: (id: string): Promise<FileItem> => dataOf(apiClient.POST("/v1/files/{file_id}/reindex", file(id))),
  /** A 15-minute link on Shosai's address; the edge streams the bytes. */
  download: (id: string): Promise<DownloadLink> => dataOf(apiClient.GET("/v1/files/{file_id}/download", file(id))),
  /** Used bytes and Leo's bytes against the plan, and the dates over the limits (FL-D2, FL-D10). */
  storage: (): Promise<StorageStanding> => dataOf(apiClient.GET("/v1/files/storage")),

  createFolder: (name: string): Promise<FileFolder> => dataOf(apiClient.POST("/v1/files/folders", { body: { name } })),
  updateFolder: (id: string, patch: FolderUpdate): Promise<FileFolder> =>
    dataOf(apiClient.PATCH("/v1/files/folders/{folder_id}", { ...folder(id), body: patch })),
  removeFolder: (id: string): Promise<void> => dataOf(apiClient.DELETE("/v1/files/folders/{folder_id}", folder(id))),
};
