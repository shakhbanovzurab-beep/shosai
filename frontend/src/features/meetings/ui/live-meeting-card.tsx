import { ArrowRight } from "lucide-react";
import { useTranslations } from "use-intl";

import { Button } from "@/components/ui/button";
import { Link } from "@/lib/navigation";

import type { Meeting } from "../domain/meeting";
import { JoinButton } from "./join-button";
import { LiveBadge, MeetingParticipants, MeetingSourceLabel } from "./meeting-meta";
import { useMeetingTimes } from "./use-meeting-times";

/**
 * The meeting happening now, set apart from everything else on the page. A call opens to join; a recording
 * in Notes opens its page with the transcript as it is written.
 */
export function LiveMeetingCard({ meeting, now }: { meeting: Meeting; now: number }) {
  const t = useTranslations("meetings");
  const room = useTranslations("meetingRoom");
  const times = useMeetingTimes();
  const titleId = `meeting-${meeting.id}`;
  const { recording } = meeting;
  return (
    <article
      aria-labelledby={titleId}
      // The tint starts in the corner where reading starts: top left, or top right in a right-to-left language.
      className="relative flex flex-col gap-5 overflow-hidden rounded-xl border border-destructive/30 bg-linear-to-br from-destructive/5 via-card to-card p-5 shadow-sm sm:flex-row sm:items-end sm:justify-between rtl:bg-linear-to-bl"
    >
      <div className="flex min-w-0 flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2 text-muted-foreground text-sm">
          <LiveBadge />
          <span>{times.ongoing(meeting, now)}</span>
        </div>
        <h3 id={titleId} dir="auto" className="font-semibold text-xl tracking-tight">
          {meeting.title || room("untitled")}
        </h3>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <MeetingSourceLabel meeting={meeting} />
          <MeetingParticipants people={meeting.participants} max={5} />
        </div>
      </div>
      {recording ? (
        <Button asChild size="lg" variant="outline" className="shrink-0">
          <Link href={`/app/notes/${recording.noteId}`}>
            {t("openRecording")}
            <ArrowRight data-icon="inline-end" className="rtl:-scale-x-100" />
          </Link>
        </Button>
      ) : (
        <JoinButton meeting={meeting} size="lg" className="shrink-0" />
      )}
    </article>
  );
}
