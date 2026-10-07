"use client";

import { cn } from "cn";
import { useTranslations } from "next-intl";

import { Checkbox } from "@/components/ui/checkbox";

import type { Task } from "../../domain/content-contract";
import type { Member, Project, Team } from "../../domain/contract";
import { toggleTask, updateTask } from "../../model/task-actions";
import { DuePicker } from "./due-picker";
import { OwnerPicker } from "./owner-picker";
import { TaskMeta } from "./task-meta";

export type TaskRowContext = {
  ws: string;
  slug: string;
  now: number;
  meId: string;
  members: Member[];
  teams: Team[];
  projects: Project[];
};

type TaskRowProps = TaskRowContext & {
  task: Task;
  /** Shows who owns it, with the picker to reassign; off where every row is the viewer's own. */
  showOwner?: boolean;
  /** Hides the link to where it came from, on that meeting's or project's own page. */
  hideSource?: "meeting" | "project";
};

/**
 * One task: tick it off, see where it came from (a meeting, a project), reschedule or hand it on by
 * clicking the due date or the owner. Changes apply at once and roll back if the server refuses.
 */
export function TaskRow({ task, ws, slug, now, meId, members, teams, projects, showOwner, hideSource }: TaskRowProps) {
  const id = `task-${task.id}`;
  const owner = members.find((m) => m.id === task.assignee_id) ?? null;
  const done = task.status === "done";
  const t = useTranslations("workspaceTasks");
  /** "Now yours", "Now owned by Maya Chen" or "Nobody owns it now", after a reassignment. */
  const ownerChanged = (ownerId: string | null) => {
    const next = members.find((m) => m.id === ownerId);
    if (!next) return t("owner.cleared");
    return next.id === meId ? t("owner.changedToYou") : t("owner.changedTo", { name: next.name });
  };

  return (
    <li className="flex flex-wrap items-start gap-x-3 gap-y-2 px-4 py-3">
      <Checkbox
        id={id}
        checked={done}
        onCheckedChange={(checked) => void toggleTask(ws, task, checked === true)}
        className="mt-0.5"
      />
      <div className="flex min-w-0 flex-1 basis-56 flex-col gap-1">
        <label
          htmlFor={id}
          dir="auto"
          className={cn("cursor-pointer text-pretty text-sm", done && "text-muted-foreground line-through")}
        >
          {task.title}
        </label>
        <TaskMeta task={task} slug={slug} teams={teams} projects={projects} hideSource={hideSource} />
      </div>
      <div className="ms-7 flex shrink-0 items-center gap-2 sm:ms-0">
        <DuePicker
          dueOn={task.due_on}
          now={now}
          done={done}
          onChange={
            done
              ? undefined
              : (due_on) => void updateTask(ws, task, { due_on }, due_on ? t("due.changed") : t("due.cleared"))
          }
        />
        {showOwner ? (
          <OwnerPicker
            owner={owner}
            members={members}
            meId={meId}
            onChange={(assignee_id) => void updateTask(ws, task, { assignee_id }, ownerChanged(assignee_id))}
          />
        ) : null}
      </div>
    </li>
  );
}
