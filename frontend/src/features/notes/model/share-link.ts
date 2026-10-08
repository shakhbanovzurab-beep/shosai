"use client";

import { toast } from "sonner";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { apiErrorDescription } from "@/lib/api/error-description";
import { copyText } from "@/lib/copy-text";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { notesApi } from "../api/notes-api";
import type { SharedCommentsResponse, ShareLinkSettings } from "../domain/share-link";
import type { CommonWords, ShareWords } from "./words";

function keyed<T>(load: (key: string) => Promise<T>) {
  const made = new Map<string, PollingResource<T>>();
  return (key: string) => {
    let resource = made.get(key);
    if (!resource) {
      resource = createPollingResource(() => load(key));
      made.set(key, resource);
    }
    return resource;
  };
}

const linkOf = keyed((noteId) => notesApi.getShareLink(noteId));
const commentsOf = keyed((token) => notesApi.listComments(token));

export const useShareLink = (noteId: string) => usePollingResource(linkOf(noteId));
export const retryShareLink = (noteId: string) => linkOf(noteId).refresh();
export const useSharedComments = (token: string) => usePollingResource(commentsOf(token));
export const retrySharedComments = (token: string) => commentsOf(token).refresh();

/** Turns the link on with `settings`, or changes what it shows; the switch moves at once and moves back if refused. */
export async function updateShareLink(noteId: string, settings: ShareLinkSettings, t: ShareWords) {
  const resource = linkOf(noteId);
  const before = resource.getSnapshot();
  const previous = before.status === "ready" ? before.data : null;
  resource.update((data) => (data.link ? { link: { ...data.link, settings } } : data));
  try {
    const saved = await notesApi.saveShareLink(noteId, settings);
    resource.update(() => saved);
  } catch (error) {
    if (previous) resource.update(() => previous);
    toast.error(t("panel.updateFailed"), { description: apiErrorDescription(error) });
  }
}

/** Turns the link off: it stops working for everyone who has it. */
export async function stopSharing(noteId: string, t: ShareWords) {
  try {
    linkOf(noteId).update(() => ({ link: null }));
    await notesApi.revokeShareLink(noteId);
    toast.success(t("panel.turnedOff"));
  } catch (error) {
    void linkOf(noteId).refresh();
    toast.error(t("panel.turnOffFailed"), { description: apiErrorDescription(error) });
  }
}

export async function copyShareLink(url: string, common: CommonWords) {
  try {
    await copyText(url);
    toast.success(common("feedback.linkCopied"));
  } catch {
    toast.error(common("feedback.linkCopyFailed"));
  }
}

/** Posts a comment under a shared meeting; true once it's there. */
export async function postSharedComment(token: string, author: string, text: string, t: ShareWords) {
  try {
    const saved: SharedCommentsResponse = await notesApi.addComment(token, author, text);
    commentsOf(token).update(() => saved);
    return true;
  } catch (error) {
    toast.error(t("comments.postFailed"), { description: apiErrorDescription(error) });
    return false;
  }
}
