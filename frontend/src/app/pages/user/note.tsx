import { useLoaderData } from "react-router";

import { PageMeta } from "@/app/root/page-meta";
import { MeetingHubChip } from "@/features/hub/ui/meeting/meeting-hub-chip";
import type { MeetingNote } from "@/features/notes/domain/types";
import { NoteDetail } from "@/features/notes/ui/note-detail";
import { ShareLinkPanel } from "@/features/notes/ui/share-link-panel";
import { RecordingShareButton } from "@/features/workspace/ui/personal/recording-share-button";
import { SharedActionItems } from "@/features/workspace/ui/personal/shared-action-items";
import { useSearchParams } from "@/lib/navigation";

/** `?t=` seconds into the recording, as "Jump to the moment" links send it. */
const parseMoment = (value: string | null) => {
  const seconds = value === null ? Number.NaN : Number(value);
  return Number.isInteger(seconds) && seconds >= 0 ? seconds : undefined;
};

export function Component() {
  const note = useLoaderData<MeetingNote>();
  const moment = parseMoment(useSearchParams().get("t"));
  // A recording can be shared into a workspace from here; once it is, its action items are the
  // workspace's tasks. Without a workspace nothing extra shows. Its hub shows under the title.
  return (
    <>
      <PageMeta title={note.title} />
      <NoteDetail
        note={note}
        moment={moment}
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
    </>
  );
}
