"use client";

import { ArrowUpRight, BookOpen } from "lucide-react";
import { useTranslations } from "use-intl";

import { LoadError } from "@/components/feedback";
import { Skeleton } from "@/components/ui/skeleton";
import { Link } from "@/lib/navigation";

import { workspacePath } from "../../domain/paths";
import type { WorkspaceKnowledge } from "../../domain/personal-contract";
import { myKnowledgeResource, useMyKnowledge } from "../../model/resources";
import { kindLabel } from "../knowledge/kind-labels";
import { KnowledgeIcon } from "../knowledge/knowledge-icon";
import { EmptyMessage } from "../shared/empty-message";

function WorkspaceBlock({ entry }: { entry: WorkspaceKnowledge }) {
  const { workspace, items } = entry;
  const t = useTranslations("workspacePersonal.knowledge");
  const tKinds = useTranslations("workspaceKnowledge");
  return (
    <section aria-labelledby={`ws-knowledge-${workspace.id}`} className="flex flex-col gap-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 id={`ws-knowledge-${workspace.id}`} className="font-medium" dir="auto">
          {workspace.name}
        </h3>
        <Link
          href={workspacePath(workspace.slug, "/knowledge")}
          className="inline-flex items-center gap-1 rounded-sm text-muted-foreground text-sm outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
        >
          {t("open")}
          <ArrowUpRight className="size-3.5 rtl:-scale-x-100" aria-hidden="true" />
        </Link>
      </div>
      <p className="text-muted-foreground text-sm">
        {t("summary", {
          meetings: entry.meetings,
          decisions: entry.decisions,
          projects: entry.projects,
          items: items.length,
        })}
      </p>
      {items.length > 0 ? (
        <ul className="divide-y rounded-xl border bg-card" aria-label={t("listLabel", { workspace: workspace.name })}>
          {items.map((item) => (
            <li key={item.id} className="flex items-center gap-3 px-4 py-2.5">
              <KnowledgeIcon kind={item.kind} />
              <span className="min-w-0 flex-1 truncate text-sm" dir="auto">
                {item.name}
              </span>
              <span className="hidden shrink-0 text-muted-foreground text-xs sm:inline">
                {kindLabel(tKinds, item.kind)}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

/**
 * In Personal, Leo also answers from what the account's workspaces share with it, exactly as it may
 * use them as a member. Read-only here: each workspace manages its own knowledge.
 */
export function WorkspaceKnowledgeForLeo() {
  const knowledge = useMyKnowledge();
  const t = useTranslations("workspacePersonal.knowledge");
  if (knowledge.status === "error")
    return (
      <LoadError
        title={t("loadFailed")}
        message={knowledge.message}
        onRetry={() => void myKnowledgeResource.refresh()}
      />
    );
  if (knowledge.status === "loading") return <Skeleton className="h-64 rounded-xl" />;
  if (knowledge.data.workspaces.length === 0)
    return <EmptyMessage icon={BookOpen} title={t("emptyTitle")} text={t("empty")} />;
  return (
    <div className="flex flex-col gap-8">
      <p className="max-w-2xl text-muted-foreground text-sm">{t("intro")}</p>
      {knowledge.data.workspaces.map((entry) => (
        <WorkspaceBlock key={entry.workspace.id} entry={entry} />
      ))}
    </div>
  );
}
