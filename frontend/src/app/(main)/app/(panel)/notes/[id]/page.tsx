import { notFound } from "next/navigation";

import type { Metadata } from "next";
import { getTranslations } from "next-intl/server";

import { MeetingHubChip } from "@/features/hub";
import { findMeetingNote, NoteDetail, ShareLinkPanel } from "@/features/notes";
import { RecordingShareButton, SharedActionItems } from "@/features/workspace";

interface PageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ t?: string | string[] }>;
}

/** `?t=` seconds into the recording, as "Jump to the moment" links send it. */
const parseMoment = (value: string | string[] | undefined) => {
  const seconds = typeof value === "string" ? Number(value) : Number.NaN;
  return Number.isInteger(seconds) && seconds >= 0 ? seconds : undefined;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { id } = await params;
  const note = findMeetingNote(id);
  const t = await getTranslations("notesNote");
  return { title: note ? note.title : t("notFound"), alternates: { canonical: `/app/notes/${id}` } };
}

export default async function Page({ params, searchParams }: PageProps) {
  const [{ id }, { t }] = await Promise.all([params, searchParams]);
  const note = findMeetingNote(id);
  if (!note) notFound();

  // A recording can be shared into a workspace from here; once it is, its action items are the
  // workspace's tasks. Without a workspace nothing extra shows. Its hub shows under the title.
  return (
    <NoteDetail
      note={note}
      moment={parseMoment(t)}
      meta={<MeetingHubChip meetingId={note.id} />}
      actions={
        <RecordingShareButton
          recordingId={note.id}
          title={note.title}
          linkShare={<ShareLinkPanel noteId={note.id} />}
        />
      }
      renderActionItems={(local) => <SharedActionItems recordingId={note.id}>{local}</SharedActionItems>}
    />
  );
}
