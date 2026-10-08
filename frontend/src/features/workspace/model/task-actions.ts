"use client";

import type { ReactNode } from "react";

import { toast } from "sonner";

import { apiErrorDescription } from "@/lib/api/error-description";

import type { Task, TaskCreate, TaskUpdate } from "../domain/content-contract";
import type { MyTask } from "../domain/personal-contract";
import { mySharesResource, myTasksResource, resourcesOf } from "./resources";
import { failureText, words } from "./words";

/* A task is one object wherever it shows: the workspace's lists, a meeting page, and its assignee's Personal. */

const updateFailed = () => words((t) => t("toasts.taskUpdateFailed"));

function replaceEverywhere(ws: string, next: Task) {
  const r = resourcesOf(ws);
  r.tasks.update((data) => ({ tasks: data.tasks.map((t) => (t.id === next.id ? next : t)) }));
  if (next.meeting_id)
    r.meeting(next.meeting_id).update((m) =>
      m ? { ...m, tasks: m.tasks.map((t) => (t.id === next.id ? next : t)) } : m,
    );
  myTasksResource.update((data) => ({
    tasks: data.tasks.map((t) => (t.id === next.id && t.workspace.id === ws ? { ...t, ...next } : t)),
  }));
}

/**
 * Applies the change at once and confirms it with the server, putting the task back as it was if the
 * server says no. Resolves to whether it stuck.
 */
export async function updateTask(ws: string, task: Task, change: TaskUpdate, success?: ReactNode) {
  replaceEverywhere(ws, { ...task, ...change });
  try {
    const saved = await resourcesOf(ws).api.updateTask(task.id, change);
    replaceEverywhere(ws, saved);
    if (success) toast.success(success);
    // Becoming someone's task, or no longer, changes their Personal view.
    if (change.assignee_id !== undefined) void myTasksResource.refresh();
    return true;
  } catch (error) {
    replaceEverywhere(ws, task);
    toast.error(updateFailed(), { description: apiErrorDescription(error) });
    return false;
  }
}

/** Ticks a task off (it moves to Done, so the toast offers Undo) or reopens it. */
export async function toggleTask(ws: string, task: Task, done: boolean) {
  const saved = await updateTask(ws, task, { status: done ? "done" : "todo" });
  if (saved && done)
    toast.success(
      words((t) => t("toasts.markedDone")),
      {
        description: task.title,
        action: {
          label: words((_, common) => common("actions.undo")),
          onClick: () => void updateTask(ws, { ...task, status: "done" }, { status: task.status }),
        },
      },
    );
}

/** The same, from Personal, where tasks come from every workspace. */
export const toggleMyTask = (task: MyTask, done: boolean) => toggleTask(task.workspace.id, task, done);

/** Adds a task; resolves to null on success or the message to show in the form. */
export async function createTask(ws: string, input: TaskCreate): Promise<string | null> {
  try {
    const task = await resourcesOf(ws).api.createTask(input);
    resourcesOf(ws).tasks.update((data) => ({ tasks: [task, ...data.tasks] }));
    if (input.assignee_id) void myTasksResource.refresh();
    toast.success(
      words((t) => t("toasts.taskAdded")),
      { description: task.title },
    );
    return null;
  } catch (error) {
    return failureText(error);
  }
}

/** Sets a task's status from somewhere that only knows its id (a shared meeting in Notes). */
export async function setTaskStatus(ws: string, taskId: string, status: Task["status"]) {
  try {
    await resourcesOf(ws).api.updateTask(taskId, { status });
    void mySharesResource.refresh();
    void myTasksResource.refresh();
    void resourcesOf(ws).tasks.refresh();
    return true;
  } catch (error) {
    toast.error(updateFailed(), { description: apiErrorDescription(error) });
    return false;
  }
}
