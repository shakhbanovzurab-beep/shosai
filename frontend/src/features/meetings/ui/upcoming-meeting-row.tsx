import { Badge } from "@/components/ui/badge";
import { Item, ItemActions, ItemContent, ItemDescription, ItemMedia, ItemTitle } from "@/components/ui/item";

import { isJoinable, type Meeting } from "../domain/meeting";
import { JoinButton } from "./join-button";
import { MeetingParticipants, MeetingSourceLabel } from "./meeting-meta";
import { useMeetingTimes } from "./use-meeting-times";

/** A scheduled meeting: start time, title and where; "In 25 min" within the hour; Join once it opens. */
export function UpcomingMeetingRow({ meeting, now }: { meeting: Meeting; now: number }) {
  const times = useMeetingTimes();
  const soon = Date.parse(meeting.start) - now < 60 * 60_000;
  return (
    <Item variant="outline" className="bg-card" role="listitem">
      {/* Wide enough for a 12-hour "10:30 AM" and a duration such as "1 hr 30 min". */}
      <ItemMedia className="w-20 flex-col items-start gap-0 whitespace-nowrap">
        <time dateTime={meeting.start} className="font-semibold tabular-nums">
          {times.time(meeting.start)}
        </time>
        <span className="text-muted-foreground text-xs">{times.duration(meeting)}</span>
      </ItemMedia>
      <ItemContent className="min-w-0">
        <ItemTitle dir="auto" className="w-full truncate">
          {meeting.title}
        </ItemTitle>
        <ItemDescription className="flex min-w-0 items-center gap-2">
          <MeetingSourceLabel meeting={meeting} />
        </ItemDescription>
      </ItemContent>
      <ItemActions className="gap-3">
        {soon ? <Badge variant="secondary">{times.startsIn(meeting, now)}</Badge> : null}
        <span className="hidden sm:block">
          <MeetingParticipants people={meeting.participants} max={3} />
        </span>
        {isJoinable(meeting, now) ? <JoinButton meeting={meeting} size="sm" /> : null}
      </ItemActions>
    </Item>
  );
}
