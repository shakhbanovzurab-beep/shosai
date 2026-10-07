"use client";

import type { ReactNode } from "react";

import Link from "next/link";

import { cn } from "cn";
import { useTranslations } from "next-intl";

import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";

import { meetingPath } from "../../domain/paths";
import { useMyShares } from "../../model/resources";
import { setTaskStatus } from "../../model/task-actions";

/**
 * A recording's action items. Once it's shared, they are the workspace's tasks: ticking one here
 * ticks it there, for everyone. Until then, `children` (the note's own list) shows.
 */
export function SharedActionItems({ recordingId, children }: { recordingId: string; children: ReactNode }) {
  const shares = useMyShares();
  const t = useTranslations("workspacePersonal.actionItems");
  const words = useTranslations("workspaceTasks");
  const share = shares.status === "ready" ? shares.data.recordings.find((r) => r.recording_id === recordingId) : null;
  if (!share || share.tasks.length === 0) return children;

  return (
    <div className="flex flex-col gap-3">
      <p className="text-muted-foreground text-xs">
        {t.rich("tracked", {
          workspace: share.workspace.name,
          link: (chunks) => (
            <Link
              href={meetingPath(share.workspace.slug, recordingId)}
              dir="auto"
              className="text-foreground underline-offset-4 hover:underline"
            >
              {chunks}
            </Link>
          ),
        })}
      </p>
      <ul className="flex flex-col gap-2.5">
        {share.tasks.map((task) => {
          const id = `shared-task-${task.id}`;
          const done = task.status === "done";
          return (
            <li key={task.id} className="flex items-start gap-3">
              <Checkbox
                id={id}
                checked={done}
                onCheckedChange={(checked) =>
                  void setTaskStatus(share.workspace.id, task.id, checked === true ? "done" : "todo")
                }
                className="mt-0.5"
              />
              <label htmlFor={id} className="flex min-w-0 flex-1 cursor-pointer flex-col gap-0.5 text-sm">
                <span dir="auto" className={cn(done && "text-muted-foreground line-through")}>
                  {task.title}
                </span>
                <span className="flex items-center gap-2 text-muted-foreground text-xs">
                  <span dir="auto">{task.assignee_name ?? words("owner.unassigned")}</span>
                  {task.status === "in_progress" ? (
                    <Badge variant="secondary">{words("status.in_progress")}</Badge>
                  ) : null}
                </span>
              </label>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
