import { getTranslations } from "next-intl/server";

import { findMeetingNote } from "../data/meeting-notes";
import { type SharedNote, toSharedNote } from "../domain/shared-note";
import { openShareLink } from "./demo-share-links";

/**
 * The meeting a share link opens, as the link shows it; null for an unknown, revoked or expired link.
 * Speakers the link keeps anonymous are numbered in the reader's interface language ("Speaker 1").
 */
export async function readSharedNote(token: string): Promise<SharedNote | null> {
  const opened = openShareLink(token);
  const note = opened ? findMeetingNote(opened.noteId) : undefined;
  if (!opened || !note) return null;
  const t = await getTranslations("notesShare");
  return toSharedNote(note, opened.link, (order) => t("page.speaker", { order }));
}
