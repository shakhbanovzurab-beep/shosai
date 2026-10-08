"use client";

import { useState } from "react";

import { CalendarClock, EllipsisVertical, Pencil, Trash2, UserRound } from "lucide-react";
import { useFormatter, useTranslations } from "use-intl";

import { ConfirmDestructive } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuItem, DropdownMenuSeparator } from "@/components/ui/dropdown-menu-items";
import { useRouter } from "@/lib/navigation";

import type { Project } from "../../domain/contract";
import { canEditProject } from "../../domain/roles";
import { deleteProject } from "../../model/group-actions";
import { useWorkspace } from "../../model/use-workspace";
import { TeamDot } from "../shared/badges";
import { ProjectDialog } from "./project-dialog";
import { ProjectStatusBadge } from "./project-meta";

/** The project's name and purpose, who leads it and by when; its lead or an admin can edit or delete it. */
export function ProjectHeader({ project }: { project: Project }) {
  const { ws, state, can, path } = useWorkspace();
  const router = useRouter();
  const t = useTranslations("workspaceProjects");
  const common = useTranslations("common");
  const format = useFormatter();
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const lead = state.members.find((m) => m.id === project.lead_id);
  const team = state.teams.find((t) => t.id === project.team_id);
  const editable = canEditProject(can.me, project);
  let leadLabel = t("noLead");
  if (lead) leadLabel = t("ledBy", { who: lead.id === state.me_id ? "me" : "member", name: lead.name });
  // A calendar day parses as UTC midnight, and next-intl formats in UTC, so the day never shifts.
  const target = project.target_date
    ? t("target.on", { date: format.dateTime(new Date(project.target_date), "medium") })
    : t("target.none");

  return (
    <header className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 dir="auto" className="text-balance font-semibold text-2xl tracking-tight">
              {project.name}
            </h1>
            <ProjectStatusBadge status={project.status} />
          </div>
          {project.description ? (
            <p dir="auto" className="max-w-2xl text-pretty text-muted-foreground text-sm">
              {project.description}
            </p>
          ) : null}
        </div>
        {editable ? (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="icon" aria-label={common("actionsFor", { name: project.name })}>
                <EllipsisVertical />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuGroup>
                <DropdownMenuItem onSelect={() => setEditing(true)}>
                  <Pencil />
                  {t("header.edit")}
                </DropdownMenuItem>
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
                <DropdownMenuItem variant="destructive" onSelect={() => setDeleting(true)}>
                  <Trash2 />
                  {t("header.delete")}
                </DropdownMenuItem>
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </div>
      <dl className="flex flex-wrap gap-x-5 gap-y-2 text-muted-foreground text-sm">
        <div className="flex items-center gap-1.5">
          <dt className="sr-only">{t("header.lead")}</dt>
          <UserRound className="size-4" aria-hidden="true" />
          <dd>{leadLabel}</dd>
        </div>
        {team ? (
          <div className="flex items-center gap-1.5">
            <dt className="sr-only">{t("header.team")}</dt>
            <TeamDot team={team} />
            <dd dir="auto">{team.name}</dd>
          </div>
        ) : null}
        <div className="flex items-center gap-1.5">
          <dt className="sr-only">{t("header.target")}</dt>
          <CalendarClock className="size-4" aria-hidden="true" />
          <dd>{target}</dd>
        </div>
      </dl>
      <ProjectDialog project={project} open={editing} onOpenChange={setEditing} />
      <ConfirmDestructive
        open={deleting}
        title={t("header.deleteTitle", { name: project.name })}
        description={t("header.deleteText")}
        confirmLabel={t("header.delete")}
        onConfirm={async () => {
          setDeleting(false);
          if (await deleteProject(ws, project.id, project.name)) router.push(path("/projects"));
        }}
        onCancel={() => setDeleting(false)}
      />
    </header>
  );
}
