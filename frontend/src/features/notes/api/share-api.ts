import { apiClient } from "@/lib/api/app-client";
import { dataOf } from "@/lib/api/client";
import type { components } from "@/lib/api/generated/schema";

import type { ShareLink, ShareLinkResponse, ShareLinkSettings } from "../domain/share-link";

type ShareLinkOut = components["schemas"]["ShareLinkOut"];

const meeting = (id: string) => ({ params: { path: { meeting_id: id } } });

const linkOf = (link: ShareLinkOut): ShareLink => ({
  token: link.token,
  path: link.path,
  settings: {
    showTranscript: link.show_transcript,
    showNames: link.show_names,
    allowComments: link.allow_comments,
    expiry: link.expiry,
  },
  expiresAt: link.expires_at ?? null,
});

const answerOf = (answer: { link?: ShareLinkOut | null }): ShareLinkResponse => ({
  link: answer.link ? linkOf(answer.link) : null,
});

/** Ссылка встречи на `/v1/notes/{id}/share-link` (план notes, шаг 13): одна на встречу, включена или нет. */
export const shareApi = {
  getShareLink: async (noteId: string): Promise<ShareLinkResponse> =>
    answerOf(await dataOf(apiClient.GET("/v1/notes/{meeting_id}/share-link", meeting(noteId)))),
  saveShareLink: async (noteId: string, settings: ShareLinkSettings): Promise<ShareLinkResponse> =>
    answerOf(
      await dataOf(
        apiClient.PUT("/v1/notes/{meeting_id}/share-link", {
          ...meeting(noteId),
          body: {
            show_transcript: settings.showTranscript,
            show_names: settings.showNames,
            allow_comments: settings.allowComments,
            expiry: settings.expiry,
          },
        }),
      ),
    ),
  revokeShareLink: async (noteId: string): Promise<ShareLinkResponse> => {
    await dataOf(apiClient.DELETE("/v1/notes/{meeting_id}/share-link", meeting(noteId)));
    return { link: null };
  },
};
