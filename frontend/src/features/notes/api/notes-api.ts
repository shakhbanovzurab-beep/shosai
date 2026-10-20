import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

import type { LibraryFolder } from "../domain/library";

type Schemas = components["schemas"];
export type MeetingCardOut = Schemas["MeetingCardOut"];
export type MeetingOut = Schemas["MeetingOut"];
export type MeetingPageOut = Schemas["Page_MeetingCardOut_"];
export type FolderOut = Schemas["FolderOut"];
export type CountsOut = Schemas["CountsOut"];
export type ImportStarted = Schemas["ImportStarted"];
export type RunOut = Schemas["RunOut"];

const meeting = (id: string) => ({ params: { path: { meeting_id: id } } });
const folder = (id: string) => ({ params: { path: { folder_id: id } } });

/** Библиотека и факты встречи на `/v1/notes*` (план notes, §3.2). */
export const notesApi = {
  page: (query: { folder?: LibraryFolder; cursor?: string; limit: number }): Promise<MeetingPageOut> =>
    dataOf(apiClient.GET("/v1/notes", { params: { query } })),
  counts: (): Promise<CountsOut> => dataOf(apiClient.GET("/v1/notes/counts")),
  meeting: (id: string): Promise<MeetingOut> => dataOf(apiClient.GET("/v1/notes/{meeting_id}", meeting(id))),
  /** Кладёт встречу в папку; null вынимает её из папки. */
  file: (id: string, folderId: string | null): Promise<MeetingOut> =>
    dataOf(apiClient.PATCH("/v1/notes/{meeting_id}", { ...meeting(id), body: { folder_id: folderId } })),
  remove: (id: string): Promise<void> => dataOf(apiClient.DELETE("/v1/notes/{meeting_id}", meeting(id))),

  folders: (cursor?: string): Promise<Schemas["Page_FolderOut_"]> =>
    dataOf(apiClient.GET("/v1/notes/folders", { params: { query: { cursor, limit: 100 } } })),
  createFolder: (name: string): Promise<FolderOut> => dataOf(apiClient.POST("/v1/notes/folders", { body: { name } })),
  renameFolder: (id: string, name: string): Promise<FolderOut> =>
    dataOf(apiClient.PATCH("/v1/notes/folders/{folder_id}", { ...folder(id), body: { name } })),
  removeFolder: (id: string): Promise<void> => dataOf(apiClient.DELETE("/v1/notes/folders/{folder_id}", folder(id))),

  /** Забирает загруженную запись: встречу и прогон, который её расшифрует. */
  importRecording: (uploadId: string): Promise<ImportStarted> =>
    dataOf(apiClient.POST("/v1/notes/imports", { body: { upload_id: uploadId } })),
  run: (runId: string): Promise<RunOut> =>
    dataOf(apiClient.GET("/v1/me/runs/{run_id}", { params: { path: { run_id: runId } } })),
};
