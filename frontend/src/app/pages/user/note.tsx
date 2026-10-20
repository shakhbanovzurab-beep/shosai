import { useLoaderData } from "react-router";

import { PageMeta } from "@/app/root/page-meta";
import { isServed } from "@/config/unserved-slices";
import { MeetingHubChip } from "@/features/hub/ui/meeting/meeting-hub-chip";
import type { MeetingPage } from "@/features/notes/domain/meeting-page";
import { useMeeting } from "@/features/notes/model/meeting-resource";
import { NoteDetail } from "@/features/notes/ui/note-detail";
import { ShareLinkPanel } from "@/features/notes/ui/share-link-panel";
import { RecordingShareButton } from "@/features/workspace/ui/personal/recording-share-button";
import { SharedActionItems } from "@/features/workspace/ui/personal/shared-action-items";
import { useSearchParams } from "@/lib/navigation";

// Чип хаба — виджет среза hubs: пока у него нет API, страница встречи его не показывает.
const HUBS_SERVED = isServed("hubs");

/** `?t=` — секунда записи, как её передают ссылки «Перейти к моменту». */
const parseMoment = (value: string | null) => {
  const seconds = value === null ? Number.NaN : Number(value);
  return Number.isInteger(seconds) && seconds >= 0 ? seconds : undefined;
};

export function Component() {
  const loaded = useLoaderData<MeetingPage>();
  // Загрузчик положил встречу в её ресурс: дальше страница живёт им — записи и папка обновляются сами.
  const state = useMeeting(loaded.id);
  const note = state.status === "ready" ? state.data : loaded;
  const moment = parseMoment(useSearchParams().get("t"));
  // Отсюда записью можно поделиться с рабочим пространством; тогда её задачи — задачи пространства. Без
  // пространства ничего лишнего не видно. Хаб встречи — под заголовком, когда у хабов есть API.
  return (
    <>
      <PageMeta title={note.title} />
      <NoteDetail
        note={note}
        moment={moment}
        meta={HUBS_SERVED ? <MeetingHubChip meetingId={note.id} /> : undefined}
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
