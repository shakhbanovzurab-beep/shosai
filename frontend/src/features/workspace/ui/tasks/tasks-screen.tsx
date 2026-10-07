"use client";

import { useState } from "react";

import { CircleCheckBig, FilterX, ListChecks, Plus } from "lucide-react";
import { useTranslations } from "next-intl";

import { LoadError } from "@/components/feedback";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useNow } from "@/hooks/use-now";

import { visibleTeams } from "../../domain/people";
import { filterTasks, isOpen, type TasksQuery, tasksSearch } from "../../domain/tasks";
import { useResources, useTasks, useWorkspace } from "../../model/use-workspace";
import { EmptyMessage } from "../shared/empty-message";
import { TeamPage, TeamPageHeader } from "../shared/layout";
import { replaceUrl } from "../shared/replace-url";
import { NewTaskDialog } from "./new-task-dialog";
import { TaskGroups } from "./task-groups";
import { TasksToolbar } from "./tasks-toolbar";

function Loading() {
  const t = useTranslations("workspaceTasks");
  return (
    <div className="flex flex-col gap-3">
      <span className="sr-only">{t("loading")}</span>
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-40 rounded-xl" />
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-28 rounded-xl" />
    </div>
  );
}

/**
 * The workspace's tasks: agreed in meetings or added to projects. Yours first, everyone's one click
 * away; your own also appear in your personal Productivity and on the Kanban board you chose.
 */
export function TasksScreen({ initialQuery }: { initialQuery: TasksQuery }) {
  const { ws, slug, state, can, path } = useWorkspace();
  const tasks = useTasks();
  const resources = useResources();
  const now = useNow();
  const [query, setQuery] = useState(initialQuery);
  const [adding, setAdding] = useState(false);
  const t = useTranslations("workspaceTasks");
  const teams = visibleTeams(state, can.me, can.admin);
  const ctx = { ws, slug, meId: state.me_id, members: state.members, teams, projects: state.projects };

  const change = (next: TasksQuery) => {
    setQuery(next);
    replaceUrl(path(`/tasks${tasksSearch(next)}`));
  };

  let body: React.ReactNode = <Loading />;
  let counts = { mine: 0, team: 0 };
  if (tasks.status === "error")
    body = <LoadError title={t("loadFailed")} message={tasks.message} onRetry={() => void resources.tasks.refresh()} />;
  else if (tasks.status === "ready" && now !== null) {
    const all = tasks.data.tasks;
    const open = all.filter(isOpen);
    counts = { mine: open.filter((t) => t.assignee_id === state.me_id).length, team: open.length };
    const shown = filterTasks(all, query, state.me_id);
    const filtered = Boolean(query.team || query.project || query.assignee);

    if (all.length === 0)
      body = (
        <EmptyMessage
          icon={ListChecks}
          title={t("empty.title")}
          text={t("empty.text")}
          action={<Button onClick={() => setAdding(true)}>{t("empty.add")}</Button>}
        />
      );
    else if (shown.length === 0 && filtered)
      body = (
        <EmptyMessage
          icon={FilterX}
          title={t("noMatch.title")}
          text={t("noMatch.text")}
          action={
            <Button variant="outline" onClick={() => change({ ...query, team: null, project: null, assignee: null })}>
              {t("noMatch.clear")}
            </Button>
          }
        />
      );
    else if (query.view === "mine" && !shown.some(isOpen))
      body = (
        <div className="flex flex-col gap-6">
          <EmptyMessage
            icon={CircleCheckBig}
            title={t("caughtUp.title")}
            text={t("caughtUp.text")}
            action={
              <Button variant="outline" onClick={() => change({ ...query, view: "team" })}>
                {t("caughtUp.seeEveryone")}
              </Button>
            }
          />
          {shown.length > 0 ? <TaskGroups items={shown} now={now} showOwner={false} {...ctx} /> : null}
        </div>
      );
    else body = <TaskGroups items={shown} now={now} showOwner={query.view === "team"} {...ctx} />;
  }

  return (
    <TeamPage>
      <TeamPageHeader
        title={t("title")}
        description={t("description")}
        actions={
          <Button onClick={() => setAdding(true)}>
            <Plus data-icon="inline-start" />
            {t("newTask")}
          </Button>
        }
      />
      <TasksToolbar
        query={query}
        counts={counts}
        teams={teams}
        projects={state.projects}
        members={state.members}
        meId={state.me_id}
        onChange={change}
      />
      {body}
      <NewTaskDialog open={adding} onOpenChange={setAdding} projectId={query.project} />
    </TeamPage>
  );
}
