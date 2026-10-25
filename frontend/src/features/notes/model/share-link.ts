"use client";

import { toast } from "sonner";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { copyText } from "@/lib/copy-text";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";
import { inDomain } from "@/lib/resource-domains";

import { shareApi } from "../api/share-api";
import type { ShareLinkResponse, ShareLinkSettings } from "../domain/share-link";
import { describeNoteError } from "./problem-words";
import type { CommonWords, NotesWords, ShareWords } from "./words";

/** Слова тостов панели: её собственные и причины отказа API заметок. */
export interface ShareLinkWords {
  share: ShareWords;
  notes: NotesWords;
}

const links = new Map<string, PollingResource<ShareLinkResponse>>();

function linkOf(noteId: string): PollingResource<ShareLinkResponse> {
  let resource = links.get(noteId);
  if (!resource) {
    resource = inDomain(
      "notes",
      createPollingResource(() => shareApi.getShareLink(noteId)),
    );
    links.set(noteId, resource);
  }
  return resource;
}

export const useShareLink = (noteId: string) => usePollingResource(linkOf(noteId));
export const retryShareLink = (noteId: string) => linkOf(noteId).refresh();

/**
 * Включает ссылку с `settings` или меняет, что она показывает. Переключатель двигается сразу, а при отказе
 * сервера возвращается; срок действия и адрес ссылки приходят из ответа.
 */
export async function updateShareLink(noteId: string, settings: ShareLinkSettings, words: ShareLinkWords) {
  const resource = linkOf(noteId);
  const before = resource.getSnapshot();
  const previous = before.status === "ready" ? before.data : null;
  resource.update((data) => (data.link ? { link: { ...data.link, settings } } : data));
  try {
    const saved = await shareApi.saveShareLink(noteId, settings);
    resource.update(() => saved);
  } catch (error) {
    if (previous) resource.update(() => previous);
    toast.error(words.share("panel.updateFailed"), { description: describeNoteError(error, words.notes) });
  }
}

/** Выключает ссылку: она перестаёт работать у всех, у кого есть, а её комментарии удаляются. */
export async function stopSharing(noteId: string, words: ShareLinkWords) {
  try {
    linkOf(noteId).update(() => ({ link: null }));
    await shareApi.revokeShareLink(noteId);
    toast.success(words.share("panel.turnedOff"));
  } catch (error) {
    void linkOf(noteId).refresh();
    toast.error(words.share("panel.turnOffFailed"), { description: describeNoteError(error, words.notes) });
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
