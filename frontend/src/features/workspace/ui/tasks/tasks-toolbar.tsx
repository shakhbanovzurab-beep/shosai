"use client";

import { useFormatter, useTranslations } from "use-intl";

import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

import type { Member, Project, Team } from "../../domain/contract";
import { TASK_VIEWS, type TasksQuery, type TaskView, UNASSIGNED } from "../../domain/tasks";
import { ProjectFilter, TeamFilter } from "../shared/filters";

const ANYONE = "anyone";

/** Mine or everyone's, then narrow by project, team and, for everyone's, by assignee. */
export function TasksToolbar({
  query,
  counts,
  teams,
  projects,
  members,
  meId,
  onChange,
}: {
  query: TasksQuery;
  counts: Record<TaskView, number>;
  teams: Team[];
  projects: Project[];
  members: Member[];
  meId: string;
  onChange: (query: TasksQuery) => void;
}) {
  const t = useTranslations("workspaceTasks");
  const format = useFormatter();
  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
      <ToggleGroup
        type="single"
        variant="outline"
        value={query.view}
        onValueChange={(value) => {
          const view = TASK_VIEWS.find((v) => v === value);
          if (view) onChange({ ...query, view, assignee: null });
        }}
        aria-label={t("views.label")}
        spacing={0}
      >
        {TASK_VIEWS.map((view) => (
          <ToggleGroupItem key={view} value={view} className="gap-2 px-3">
            {t(`views.${view}`)}
            <span className="text-muted-foreground text-xs tabular-nums">{format.number(counts[view])}</span>
          </ToggleGroupItem>
        ))}
      </ToggleGroup>
      <div className="flex flex-col gap-2 sm:flex-row">
        <ProjectFilter
          projects={projects}
          value={query.project}
          onChange={(project) => onChange({ ...query, project })}
        />
        <TeamFilter teams={teams} value={query.team} onChange={(team) => onChange({ ...query, team })} />
        {query.view === "team" ? (
          <Select
            value={query.assignee ?? ANYONE}
            onValueChange={(value) => onChange({ ...query, assignee: value === ANYONE ? null : value })}
          >
            <SelectTrigger aria-label={t("assignee.label")} className="w-full sm:w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value={ANYONE}>{t("assignee.anyone")}</SelectItem>
                <SelectItem value={UNASSIGNED}>{t("owner.unassigned")}</SelectItem>
                {members.map((member) => (
                  <SelectItem key={member.id} value={member.id}>
                    <span dir="auto">
                      {member.id === meId ? t("owner.meOption", { name: member.name }) : member.name}
                    </span>
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        ) : null}
      </div>
    </div>
  );
}
