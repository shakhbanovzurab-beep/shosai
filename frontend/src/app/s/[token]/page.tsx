import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { SharedLinkGone, SharedNoteScreen } from "@/features/notes";
import { readSharedNote } from "@/features/notes/server";

interface PageProps {
  params: Promise<{ token: string }>;
}

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { token } = await params;
  const [note, t] = await Promise.all([readSharedNote(token), getTranslations("notesShare")]);
  // A shared meeting is for the people who have the link, never for search engines.
  return { title: note ? note.title : t("page.unavailable"), robots: { index: false, follow: false } };
}

export default async function Page({ params }: PageProps) {
  const { token } = await params;
  const note = await readSharedNote(token);
  return note ? <SharedNoteScreen note={note} /> : <SharedLinkGone />;
}
