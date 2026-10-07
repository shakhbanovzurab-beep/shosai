import { NextResponse } from "next/server";

import { getTranslations } from "next-intl/server";
import { z } from "zod";

import { forwardToBackend } from "@/server/backend-proxy";

import { findMeetingNote } from "../data/meeting-notes";
import {
  SHARE_EXPIRIES,
  SHARED_AUTHOR_MAX,
  SHARED_COMMENT_MAX,
  type SharedCommentsResponse,
  type ShareLinkResponse,
} from "../domain/share-link";
import {
  addComment,
  getShareLink,
  listComments,
  openShareLink,
  revokeShareLink,
  saveShareLink,
} from "./demo-share-links";
import { refuse } from "./problems";

type NoteContext = { params: Promise<{ id: string }> };
type TokenContext = { params: Promise<{ token: string }> };

const settingsSchema = z.object({
  showTranscript: z.boolean(),
  showNames: z.boolean(),
  allowComments: z.boolean(),
  expiry: z.enum(SHARE_EXPIRIES),
});
const commentSchema = z.object({
  author: z.string().trim().max(SHARED_AUTHOR_MAX),
  text: z.string().trim().min(1).max(SHARED_COMMENT_MAX),
});

const linkPath = (id: string) => `/v1/notes/${encodeURIComponent(id)}/share-link`;

/** /api/notes/:id/share-link: the meeting's link for people outside it, and what the link shows. */
export const shareLinkRoute = {
  async GET(request: Request, { params }: NoteContext) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, linkPath(id));
    if (upstream) return upstream;
    if (!findMeetingNote(id)) return refuse("meetingNotFound", 404);
    return NextResponse.json<ShareLinkResponse>({ link: getShareLink(id) });
  },

  async PUT(request: Request, { params }: NoteContext) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, linkPath(id));
    if (upstream) return upstream;
    if (!findMeetingNote(id)) return refuse("meetingNotFound", 404);
    const body = settingsSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return refuse("linkSettingsInvalid", 422);
    return NextResponse.json<ShareLinkResponse>({ link: saveShareLink(id, body.data) });
  },

  async DELETE(request: Request, { params }: NoteContext) {
    const { id } = await params;
    const upstream = await forwardToBackend(request, linkPath(id));
    if (upstream) return upstream;
    revokeShareLink(id);
    return NextResponse.json<ShareLinkResponse>({ link: null });
  },
};

/** /api/s/:token/comments: replies on a shared meeting, open to anyone with the link while it allows them. */
export const sharedCommentsRoute = {
  async GET(request: Request, { params }: TokenContext) {
    const { token } = await params;
    const upstream = await forwardToBackend(request, `/v1/shared/${encodeURIComponent(token)}/comments`);
    if (upstream) return upstream;
    const opened = openShareLink(token);
    if (!opened?.link.settings.allowComments) return refuse("commentsClosed", 404);
    return NextResponse.json<SharedCommentsResponse>({ comments: listComments(token) });
  },

  async POST(request: Request, { params }: TokenContext) {
    const { token } = await params;
    const upstream = await forwardToBackend(request, `/v1/shared/${encodeURIComponent(token)}/comments`);
    if (upstream) return upstream;
    const opened = openShareLink(token);
    if (!opened?.link.settings.allowComments) return refuse("commentsClosed", 404);
    const body = commentSchema.safeParse(await request.json().catch(() => null));
    if (!body.success) return refuse("commentInvalid", 422);
    // A comment without a name is signed "Guest" in the language of the person who posts it, like a name typed.
    const t = await getTranslations("notesShare");
    addComment(token, body.data.author || t("comments.guest"), body.data.text);
    return NextResponse.json<SharedCommentsResponse>({ comments: listComments(token) });
  },
};
