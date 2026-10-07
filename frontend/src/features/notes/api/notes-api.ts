import { apiRequest, jsonBody } from "@/lib/api-client";

import type { MyNotesResponse } from "../domain/manual-notes";
import type { SharedCommentsResponse, ShareLinkResponse, ShareLinkSettings } from "../domain/share-link";

const notePath = (noteId: string, rest: string) => `/api/notes/${encodeURIComponent(noteId)}/${rest}`;
const commentsPath = (token: string) => `/api/s/${encodeURIComponent(token)}/comments`;

export const notesApi = {
  getMyNotes: (noteId: string) => apiRequest<MyNotesResponse>(notePath(noteId, "my-notes")),
  saveMyNotes: (noteId: string, text: string) =>
    apiRequest<MyNotesResponse>(notePath(noteId, "my-notes"), jsonBody("PUT", { text })),

  getShareLink: (noteId: string) => apiRequest<ShareLinkResponse>(notePath(noteId, "share-link")),
  saveShareLink: (noteId: string, settings: ShareLinkSettings) =>
    apiRequest<ShareLinkResponse>(notePath(noteId, "share-link"), jsonBody("PUT", settings)),
  revokeShareLink: (noteId: string) =>
    apiRequest<ShareLinkResponse>(notePath(noteId, "share-link"), { method: "DELETE" }),

  listComments: (token: string) => apiRequest<SharedCommentsResponse>(commentsPath(token)),
  addComment: (token: string, author: string, text: string) =>
    apiRequest<SharedCommentsResponse>(commentsPath(token), jsonBody("POST", { author, text })),
};
