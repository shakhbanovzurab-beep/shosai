"use client";

import { Building2, CircleAlert, FolderKanban, UserRoundMinus } from "lucide-react";
import { useFormatter, useLocale, useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/spinner";
import { formatBytes } from "@/i18n/format-units";
import { Link } from "@/lib/navigation";

import type { Member, Project, Team } from "../../domain/contract";
import type { KnowledgeItem } from "../../domain/knowledge-contract";
import { projectPath } from "../../domain/paths";
import { TeamDot } from "../shared/badges";
import { kindLabel } from "./kind-labels";
import { KnowledgeIcon } from "./knowledge-icon";
import { KnowledgeItemMenu } from "./knowledge-item-menu";
import { accessText, addedText, originText, whoAdded } from "./knowledge-words";

/** What every row needs from the workspace. */
export type KnowledgeCtx = {
  ws: string;
  slug: string;
  now: number;
  me: Member;
  admin: boolean;
  members: Member[];
  teams: Team[];
  projects: Project[];
  workspaceName: string;
};

function Status({ item }: { item: KnowledgeItem }) {
  const t = useTranslations("workspaceKnowledge");
  if (item.status === "indexing")
    return (
      <Badge variant="secondary" className="font-normal">
        <Spinner />
        {item.source.kind === "connector" ? t("status.syncing") : t("status.indexing")}
      </Badge>
    );
  if (item.status === "failed")
    return (
      <Badge variant="destructive" className="font-normal">
        <CircleAlert />
        {t("status.failed")}
      </Badge>
    );
  return null;
}

/** A file or source Leo answers from: what it is, who owns it, who it's for and the project it belongs to. */
export function KnowledgeRow({
  item,
  ctx,
  showProject,
}: {
  item: KnowledgeItem;
  ctx: KnowledgeCtx;
  showProject: boolean;
}) {
  const t = useTranslations("workspaceKnowledge");
  const format = useFormatter();
  const locale = useLocale();
  const team = item.access.level === "team" ? ctx.teams.find((t) => t.id === item.access.team_id) : undefined;
  const project = showProject ? ctx.projects.find((p) => p.id === item.project_id) : undefined;
  const who = whoAdded(item, ctx.members, ctx.me.id);
  // A shared file leaves with its owner; uploads and sources stay with the workspace.
  const leaves = item.source.kind === "personal" ? t("leaves", who) : null;
  let size: string | null = null;
  if (item.size_bytes !== null) size = formatBytes(locale, item.size_bytes);
  else if (item.page_count) size = t("pages", { count: item.page_count });
  const meta = [
    kindLabel(t, item.kind),
    size,
    originText(t, item, who, ctx.workspaceName),
    addedText(t, format, item.added_at, ctx.now),
  ];

  return (
    <li className="flex items-center gap-3 px-4 py-3">
      <KnowledgeIcon kind={item.kind} />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span dir="auto" className="truncate font-medium text-sm">
          {item.name}
        </span>
        <span className="truncate text-muted-foreground text-xs">{meta.filter(Boolean).join(" · ")}</span>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Status item={item} />
        {leaves ? (
          <span className="hidden text-muted-foreground md:inline-flex" title={leaves}>
            <UserRoundMinus className="size-4" aria-hidden="true" />
            <span className="sr-only">{leaves}</span>
          </span>
        ) : null}
        {project ? (
          <Badge variant="secondary" className="hidden font-normal lg:inline-flex" asChild>
            <Link href={projectPath(ctx.slug, project.id)}>
              <FolderKanban aria-hidden="true" />
              <span dir="auto">{project.name}</span>
            </Link>
          </Badge>
        ) : null}
        <Badge variant="outline" className="hidden font-normal sm:inline-flex">
          {team ? <TeamDot team={team} /> : <Building2 aria-hidden="true" />}
          <span dir="auto">{accessText(t, item.access, ctx.teams, ctx.workspaceName)}</span>
        </Badge>
        {ctx.admin || item.added_by === ctx.me.id ? <KnowledgeItemMenu item={item} ctx={ctx} who={who} /> : null}
      </div>
    </li>
  );
}
