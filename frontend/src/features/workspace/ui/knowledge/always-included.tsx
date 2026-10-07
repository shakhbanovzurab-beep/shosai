"use client";

import Link from "next/link";

import { FolderKanban, Gavel, Video } from "lucide-react";
import { useTranslations } from "next-intl";

import { useDecisions, useMeetings, useWorkspace } from "../../model/use-workspace";

/**
 * What Leo knows here without anyone adding it: the meetings, decisions and projects each person
 * can open. Counts are the viewer's own, so they never reveal what others can see.
 */
export function AlwaysIncluded() {
  const { state, path } = useWorkspace();
  const meetings = useMeetings();
  const decisions = useDecisions();
  const t = useTranslations("workspaceKnowledge");
  // While a list loads, its link reads "Meetings" without a count.
  const items = [
    {
      href: path("/meetings"),
      icon: Video,
      label:
        meetings.status === "ready"
          ? t("alwaysIncluded.meetings", { count: meetings.data.meetings.length })
          : t("alwaysIncluded.meetingsLoading"),
    },
    {
      href: path("/decisions"),
      icon: Gavel,
      label:
        decisions.status === "ready"
          ? t("alwaysIncluded.decisions", { count: decisions.data.decisions.length })
          : t("alwaysIncluded.decisionsLoading"),
    },
    {
      href: path("/projects"),
      icon: FolderKanban,
      label: t("alwaysIncluded.projects", { count: state.projects.length }),
    },
  ];

  return (
    <div className="flex flex-col gap-3 rounded-xl border bg-card px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-pretty text-muted-foreground text-sm">{t("alwaysIncluded.text")}</p>
      <ul className="flex shrink-0 flex-wrap gap-x-4 gap-y-1 text-sm" aria-label={t("alwaysIncluded.label")}>
        {items.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className="inline-flex items-center gap-1.5 rounded-sm font-medium tabular-nums outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring"
            >
              <item.icon className="size-4 text-muted-foreground" aria-hidden="true" />
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
