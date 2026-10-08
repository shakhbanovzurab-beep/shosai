"use client";

import { cn } from "cn";
import { useTranslations } from "use-intl";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { useNow } from "@/hooks/use-now";
import { Link } from "@/lib/navigation";

import type { DueTone } from "../../domain/format";
import { workspacePath } from "../../domain/paths";
import type { MyTask } from "../../domain/personal-contract";
import { groupTasks } from "../../domain/tasks";
import { myTasksResource, useMyTasks, useWorkspaces } from "../../model/resources";
import { toggleMyTask } from "../../model/task-actions";
import { WorkspaceTile } from "../switcher/workspace-tile";
import { useDueWords } from "../tasks/use-due-words";

const TONE: Record<DueTone, "destructive" | "secondary" | "outline"> = {
  overdue: "destructive",
  today: "secondary",
  soon: "outline",
  later: "outline",
};

function Row({ task, now }: { task: MyTask; now: number }) {
  const id = `my-task-${task.workspace.id}-${task.id}`;
  const t = useTranslations("workspaceTasks.status");
  const due = useDueWords().label(task.due_on, now);
  const source = task.project_name ?? task.meeting_title;
  return (
    <li className="flex items-center gap-3 p-4">
      <Checkbox id={id} checked={task.status === "done"} onCheckedChange={(c) => void toggleMyTask(task, c === true)} />
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <label
          htmlFor={id}
          dir="auto"
          className={cn("cursor-pointer truncate text-sm", task.status === "done" && "line-through")}
        >
          {task.title}
        </label>
        <Link
          href={workspacePath(task.workspace.slug, "/tasks")}
          className="flex min-w-0 items-center gap-1.5 text-muted-foreground text-xs underline-offset-4 hover:text-foreground hover:underline"
        >
          <WorkspaceTile name={task.workspace.name} className="size-4 text-[9px]" />
          <span className="truncate" dir="auto">
            {task.workspace.name}
            {source ? ` · ${source}` : null}
          </span>
        </Link>
      </div>
      {task.status === "in_progress" ? <Badge variant="secondary">{t("in_progress")}</Badge> : null}
      {due ? (
        <Badge variant={TONE[due.tone]} className="shrink-0 font-normal">
          {due.text}
        </Badge>
      ) : null}
    </li>
  );
}

/**
 * Your tasks from every workspace, in Personal: the workspace's own tasks, not copies, so ticking one
 * here ticks it for the team. Shows nothing for an account without workspaces.
 */
export function MyWorkspaceTasks() {
  const workspaces = useWorkspaces();
  const tasks = useMyTasks();
  const now = useNow();
  const t = useTranslations("workspacePersonal.myTasks");
  const common = useTranslations("common");
  if (workspaces.status !== "ready" || workspaces.data.workspaces.length === 0 || now === null) return null;

  let body: React.ReactNode = <Skeleton className="h-32 rounded-xl" />;
  if (tasks.status === "error")
    body = (
      <p className="rounded-xl border border-dashed p-4 text-muted-foreground text-sm">
        {t("loadFailed")}{" "}
        <Button variant="link" className="h-auto p-0" onClick={() => void myTasksResource.refresh()}>
          {common("actions.retry")}
        </Button>
      </p>
    );
  else if (tasks.status === "ready") {
    const open = groupTasks(tasks.data.tasks, now).groups.flatMap((g) => g.items);
    body =
      open.length === 0 ? (
        <p className="rounded-xl border border-dashed p-4 text-center text-muted-foreground text-sm">{t("empty")}</p>
      ) : (
        <ul className="divide-y overflow-hidden rounded-xl border bg-background shadow-xs">
          {open.slice(0, 6).map((task) => (
            <Row key={`${task.workspace.id}-${task.id}`} task={task} now={now} />
          ))}
        </ul>
      );
  }

  return (
    <section aria-labelledby="workspace-tasks" className="flex flex-col gap-2">
      <div className="flex items-baseline justify-between gap-4">
        <h3 id="workspace-tasks" className="font-medium text-muted-foreground text-xs uppercase tracking-wide">
          {t("title")}
        </h3>
        <Link
          href="/app/kanban"
          className="text-muted-foreground text-sm underline-offset-4 hover:text-foreground hover:underline"
        >
          {t("onKanban")}
        </Link>
      </div>
      {body}
    </section>
  );
}
