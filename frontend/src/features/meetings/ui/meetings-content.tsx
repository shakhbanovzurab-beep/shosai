import { type ReactNode, useId } from "react";

import Link from "next/link";

import { useTranslations } from "next-intl";

import { ItemGroup } from "@/components/ui/item";

import {
  groupByDay,
  type Meeting,
  type MeetingBuckets,
  type MeetingsView,
  overviewSections,
  viewHref,
} from "../domain/meeting";
import { LiveMeetingCard } from "./live-meeting-card";
import { MeetingsEmpty } from "./meetings-empty";
import { RecentMeetingCard } from "./recent-meeting-card";
import { UpcomingMeetingRow } from "./upcoming-meeting-row";
import { useMeetingTimes } from "./use-meeting-times";

function Section({ title, more, children }: { title: string; more?: MeetingsView; children: ReactNode }) {
  const t = useTranslations("meetings");
  const id = useId();
  return (
    <section aria-labelledby={id} className="flex flex-col gap-3">
      <div className="flex items-baseline justify-between gap-3">
        <h2 id={id} className="font-medium text-muted-foreground text-xs uppercase tracking-wide">
          {title}
        </h2>
        {more ? (
          <Link href={viewHref(more)} scroll={false} className="text-muted-foreground text-sm hover:text-foreground">
            {t("viewAll")}
          </Link>
        ) : null}
      </div>
      {children}
    </section>
  );
}

const UpcomingList = ({ meetings, now }: { meetings: Meeting[]; now: number }) => (
  <ItemGroup className="gap-2">
    {meetings.map((m) => (
      <UpcomingMeetingRow key={m.id} meeting={m} now={now} />
    ))}
  </ItemGroup>
);

const RecentGrid = ({ meetings, now }: { meetings: Meeting[]; now: number }) => (
  <div className="grid gap-3 md:grid-cols-2">
    {meetings.map((m) => (
      <RecentMeetingCard key={m.id} meeting={m} now={now} />
    ))}
  </div>
);

const LiveList = ({ meetings, now }: { meetings: Meeting[]; now: number }) => (
  <div className="flex flex-col gap-3">
    {meetings.map((m) => (
      <LiveMeetingCard key={m.id} meeting={m} now={now} />
    ))}
  </div>
);

/** Today (live, then the rest of the day), the next few days, and the latest recaps. */
function Overview({ buckets, now }: { buckets: MeetingBuckets; now: number }) {
  const t = useTranslations("meetings");
  const { live, laterToday, upcoming, recent } = overviewSections(buckets, now);
  if (live.length + buckets.upcoming.length + buckets.past.length === 0) return <MeetingsEmpty kind="none" />;
  return (
    <div className="flex flex-col gap-8">
      <Section title={t("day.today")}>
        {live.length > 0 ? <LiveList meetings={live} now={now} /> : null}
        {laterToday.length > 0 ? <UpcomingList meetings={laterToday} now={now} /> : null}
        {live.length + laterToday.length === 0 ? (
          <p className="rounded-xl border border-dashed px-4 py-6 text-center text-muted-foreground text-sm">
            {t("noMoreToday")}
          </p>
        ) : null}
      </Section>
      {upcoming.length > 0 ? (
        <Section title={t("views.upcoming")} more="upcoming">
          <UpcomingList meetings={upcoming} now={now} />
        </Section>
      ) : null}
      {recent.length > 0 ? (
        <Section title={t("recent")} more="past">
          <RecentGrid meetings={recent} now={now} />
        </Section>
      ) : null}
    </div>
  );
}

/** Upcoming meetings under their days: "Today", "Tomorrow", "Wed, Oct 8". */
function ByDay({ meetings, now }: { meetings: Meeting[]; now: number }) {
  const times = useMeetingTimes();
  return (
    <div className="flex flex-col gap-8">
      {groupByDay(meetings).map((group) => (
        <Section key={group.day.getTime()} title={times.day(group.day, now)}>
          <UpcomingList meetings={group.meetings} now={now} />
        </Section>
      ))}
    </div>
  );
}

/** The list for the chosen filter. */
export function MeetingsContent({ view, buckets, now }: { view: MeetingsView; buckets: MeetingBuckets; now: number }) {
  if (view === "all") return <Overview buckets={buckets} now={now} />;
  if (view === "live")
    return buckets.live.length > 0 ? <LiveList meetings={buckets.live} now={now} /> : <MeetingsEmpty kind="live" />;

  const meetings = buckets[view];
  if (meetings.length === 0) return <MeetingsEmpty kind={view} />;
  // Past cards carry their own date, so they need no day headings.
  if (view === "past") return <RecentGrid meetings={meetings} now={now} />;
  return <ByDay meetings={meetings} now={now} />;
}
