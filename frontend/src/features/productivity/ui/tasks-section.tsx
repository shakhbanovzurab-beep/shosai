"use client";

import { TodayTasks } from "@/features/kanban/ui/today/today-tasks";
import { MyWorkspaceTasks } from "@/features/workspace/ui/personal/my-workspace-tasks";

/** The day's tasks: your own Today, then what your workspaces assigned to you (live, not copies). */
export function TasksSection() {
  return (
    <div className="flex flex-col gap-4">
      <TodayTasks />
      <MyWorkspaceTasks />
    </div>
  );
}
