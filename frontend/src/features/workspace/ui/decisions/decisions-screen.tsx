"use client";

import { useState } from "react";

import { FilterX, Gavel } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useNow } from "@/hooks/use-now";
import { CALENDAR_DAY } from "@/i18n/calendar-days";
import { Link } from "@/lib/navigation";

import type { Decision } from "../../domain/content-contract";
import { filterDecisions, type LibraryQuery, librarySearch } from "../../domain/library";
import { visibleTeams } from "../../domain/people";
import { useDecisions, useResources, useWorkspace } from "../../model/use-workspace";
import { LibraryToolbar } from "../meetings/library-toolbar";
import { EmptyMessage } from "../shared/empty-message";
import { TeamPage, TeamPageHeader, TeamSection } from "../shared/layout";
import { replaceUrl } from "../shared/replace-url";
import { slugId } from "../shared/slug-id";
import { DecisionItem } from "./decision-item";

/** Newest first, under month headings; a month is "2026-10" in UTC, like the timestamps and their formatting. */
function byMonth(decisions: Decision[]) {
  const groups: { month: string; items: Decision[] }[] = [];
  for (const decision of decisions.toSorted((a, b) => b.decided_at.localeCompare(a.decided_at))) {
    const month = decision.decided_at.slice(0, 7);
    const last = groups.at(-1);
    if (last?.month === month) last.items.push(decision);
    else groups.push({ month, items: [decision] });
  }
  return groups;
}

/** The decision log: what the team agreed, where, and what was later replaced, without rewatching anything. */
export function DecisionsScreen({ initialQuery }: { initialQuery: LibraryQuery }) {
  const { slug, state, can, path } = useWorkspace();
  const t = useTranslations("workspaceDecisions");
  const format = useFormatter();
  // "October 2026", in the interface language: месяц — календарный, его первое число печатается в UTC.
  const monthLabel = (month: string) =>
    format.dateTime(new Date(`${month}-01T00:00:00Z`), { month: "long", year: "numeric", ...CALENDAR_DAY });
  const decisions = useDecisions();
  const resources = useResources();
  const now = useNow();
  const [query, setQuery] = useState(initialQuery);
  const teams = visibleTeams(state, can.me, can.admin);

  const change = (next: LibraryQuery) => {
    setQuery(next);
    replaceUrl(path(`/decisions${librarySearch(next)}`));
  };

  let body: React.ReactNode = (
    <div className="flex flex-col gap-3">
      <span className="sr-only">{t("loading")}</span>
      <Skeleton className="h-4 w-28" />
      <Skeleton className="h-24 rounded-xl" />
      <Skeleton className="h-24 rounded-xl" />
    </div>
  );
  if (decisions.status === "error")
    body = (
      <LoadError
        title={t("loadFailed")}
        message={decisions.message}
        onRetry={() => void resources.decisions.refresh()}
      />
    );
  else if (decisions.status === "ready" && now !== null) {
    const all = decisions.data.decisions;
    const byId = new Map(all.map((d) => [d.id, d]));
    const shown = filterDecisions(all, query);
    if (all.length === 0)
      body = (
        <EmptyMessage
          icon={Gavel}
          title={t("empty.title")}
          text={t("empty.text")}
          action={
            <Button asChild variant="outline">
              <Link href={path("/meetings")}>{t("empty.action")}</Link>
            </Button>
          }
        />
      );
    else if (shown.length === 0)
      body = (
        <EmptyMessage
          icon={FilterX}
          title={t("noMatch.title")}
          text={t("noMatch.text")}
          action={
            <Button variant="outline" onClick={() => change({ ...query, team: null, q: "" })}>
              {t("noMatch.clear")}
            </Button>
          }
        />
      );
    else
      body = (
        <div className="flex flex-col gap-8">
          {byMonth(shown).map((group) => (
            <TeamSection key={group.month} id={slugId("decisions", group.month)} title={monthLabel(group.month)}>
              <ul className="flex flex-col gap-3">
                {group.items.map((decision) => (
                  <DecisionItem
                    key={decision.id}
                    decision={decision}
                    replacement={decision.superseded_by ? byId.get(decision.superseded_by) : undefined}
                    teams={state.teams}
                    slug={slug}
                    now={now}
                  />
                ))}
              </ul>
            </TeamSection>
          ))}
        </div>
      );
  }

  return (
    <TeamPage>
      <TeamPageHeader title={t("title")} description={t("description")} />
      <LibraryToolbar query={query} teams={teams} onChange={change} searchLabel={t("searchLabel")} />
      {body}
    </TeamPage>
  );
}
