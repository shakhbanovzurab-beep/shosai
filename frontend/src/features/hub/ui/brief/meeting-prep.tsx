"use client";

import Link from "next/link";

import { FileText } from "lucide-react";
import { useFormatter, useTranslations } from "next-intl";

import type { MeetingPrep, ThreadSummary } from "../../domain/contract";
import { hubPath, threadPath } from "../../domain/paths";
import { retry, usePreps } from "../../model/hooks";
import { Block, BlockError } from "../shared/block";
import { useHubPhrases } from "../shared/phrases";
import { GapIcon } from "../shared/urgency";

/** The viewer's own time zone, from the browser. */
const viewerTimeZone = () => Intl.DateTimeFormat().resolvedOptions().timeZone;

function Part({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <h4 className="text-muted-foreground text-xs">{title}</h4>
      {children}
    </div>
  );
}

/** Before a meeting whose hub is known: what's open there, what the last meeting changed, and the materials. */
export function PrepCard({ prep }: { prep: MeetingPrep }) {
  const t = useTranslations("hubMeetings");
  const blocks = useTranslations("hubBlocks");
  const format = useFormatter();
  const say = useHubPhrases();
  const digest = prep.lastDigest;
  const lastTime: { label: string; list: ThreadSummary[] }[] = digest
    ? [
        { label: blocks("digest.untouched"), list: digest.untouched },
        { label: blocks("digest.opened"), list: digest.opened },
        { label: blocks("digest.closed"), list: digest.closed },
      ].filter(({ list }) => list.length > 0)
    : [];
  // When the meeting starts, on the viewer's own clock. Preps load in the browser only (the server
  // renders the loading state), so the viewer's time zone never meets the server's markup.
  const startsAt = format.dateTime(new Date(prep.startsAt), "weekdayDateTime", { timeZone: viewerTimeZone() });
  return (
    <article className="flex flex-col gap-4 rounded-xl border p-4" aria-label={prep.meetingTitle}>
      <header className="flex flex-col gap-0.5">
        <p className="text-muted-foreground text-xs">{t("brief.prepFor", { date: startsAt })}</p>
        <h3 dir="auto" className="font-medium text-sm">
          {prep.meetingTitle}
        </h3>
        <Link
          href={hubPath(prep.hub.id)}
          dir="auto"
          className="w-fit text-muted-foreground text-xs underline-offset-4 hover:underline"
        >
          {prep.hub.name}
        </Link>
      </header>
      {prep.open.length > 0 ? (
        <Part title={t("brief.prepOpen")}>
          <ul className="flex flex-col gap-1.5">
            {prep.open.map((thread) => (
              <li key={thread.id} className="flex items-start gap-2 text-sm">
                {thread.gap ? (
                  <GapIcon kind={thread.gap.kind} className="mt-0.5" />
                ) : (
                  <span className="w-3.5 shrink-0" />
                )}
                <span className="min-w-0">
                  <Link
                    href={threadPath(thread.hubId, thread.id)}
                    dir="auto"
                    className="underline-offset-4 hover:underline"
                  >
                    {thread.subject}
                  </Link>
                  <span className="block text-muted-foreground text-xs">{say.status(thread)}</span>
                </span>
              </li>
            ))}
          </ul>
        </Part>
      ) : null}
      {digest && lastTime.length > 0 ? (
        <Part title={t("brief.prepLast", { date: say.date(digest.meetingStartedAt) })}>
          <dl className="flex flex-col gap-1 text-sm">
            {lastTime.map(({ label, list }) => (
              <div key={label} className="flex gap-2">
                <dt className="shrink-0 text-muted-foreground">{label}:</dt>
                <dd className="min-w-0">
                  {format.list(
                    list.map((thread) => thread.subject),
                    { type: "unit", style: "short" },
                  )}
                </dd>
              </div>
            ))}
          </dl>
        </Part>
      ) : null}
      {prep.materials.length > 0 ? (
        <Part title={t("brief.prepMaterials")}>
          <ul className="flex flex-col gap-1">
            {prep.materials.map((material) => (
              <li key={material.id} className="flex items-center gap-2 text-sm">
                <FileText className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                {material.url ? (
                  <Link href={material.url} dir="auto" className="truncate underline-offset-4 hover:underline">
                    {material.title}
                  </Link>
                ) : (
                  <span dir="auto" className="truncate">
                    {material.title}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </Part>
      ) : null}
    </article>
  );
}

/** Upcoming meetings with a known hub, prepared ahead rather than five minutes before. No card when there's nothing to say. */
export function ComingUp() {
  const t = useTranslations("hubMeetings");
  const api = useTranslations("hubApi");
  const state = usePreps();
  if (state.status === "error")
    return (
      <Block id="coming-up" title={t("brief.prepTitle")}>
        <BlockError title={api("errors.unknown")} onRetry={() => void retry.preps()} />
      </Block>
    );
  if (state.status !== "ready" || state.data.preps.length === 0) return null;
  return (
    <Block id="coming-up" title={t("brief.prepTitle")}>
      <div className="flex flex-col gap-3">
        {state.data.preps.map((prep) => (
          <PrepCard key={prep.sessionOrEventId} prep={prep} />
        ))}
      </div>
    </Block>
  );
}
