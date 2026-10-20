import { apiRequest, jsonBody } from "@/lib/api/request";

import type { SharedCommentsResponse, ShareLinkResponse, ShareLinkSettings } from "../domain/share-link";

// Ссылка встречи и её комментарии на образцах `/api/…`, пока шаг 19 плана notes не переведёт их на `/v1`.
const notePath = (noteId: string, rest: string) => `/api/notes/${encodeURIComponent(noteId)}/${rest}`;
const commentsPath = (token: string) => `/api/s/${encodeURIComponent(token)}/comments`;

export const shareApi = {
  getShareLink: (noteId: string) => apiRequest<ShareLinkResponse>(notePath(noteId, "share-link")),
  saveShareLink: (noteId: string, settings: ShareLinkSettings) =>
    apiRequest<ShareLinkResponse>(notePath(noteId, "share-link"), jsonBody("PUT", settings)),
  revokeShareLink: (noteId: string) =>
    apiRequest<ShareLinkResponse>(notePath(noteId, "share-link"), { method: "DELETE" }),

  listComments: (token: string) => apiRequest<SharedCommentsResponse>(commentsPath(token)),
  addComment: (token: string, author: string, text: string) =>
    apiRequest<SharedCommentsResponse>(commentsPath(token), jsonBody("POST", { author, text })),
};
