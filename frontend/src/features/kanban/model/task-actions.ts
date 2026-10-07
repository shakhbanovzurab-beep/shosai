"use client";

import { toast } from "sonner";

import { errorMessage } from "@/lib/errors";

import { kanbanApi } from "../api/kanban-api";
import type { Task } from "../domain/board";
import type { LayoutUpdate, TaskCreate, TaskPatch } from "../domain/contract";
import { adjustTaskCount } from "./boards-resource";
import type { KanbanWords } from "./words";

/*
 * Task changes the board has already shown: each resolves to false (or null) after reporting a
 * failure, so the caller can put the board back. On a Jira board the server applies them in Jira.
 */

async function attempt<T>(title: string, run: () => Promise<T>): Promise<T | null> {
  try {
    return await run();
  } catch (error) {
    toast.error(title, { description: errorMessage(error) });
    return null;
  }
}

export async function createTask(boardId: string, request: TaskCreate, t: KanbanWords): Promise<Task | null> {
  const task = await attempt(t("errors.addTask"), () => kanbanApi.createTask(boardId, request));
  if (task) adjustTaskCount(boardId, 1);
  return task;
}

export async function patchTask(boardId: string, taskId: string, patch: TaskPatch, t: KanbanWords) {
  return (await attempt(t("errors.saveChange"), () => kanbanApi.patchTask(boardId, taskId, patch))) !== null;
}

export async function deleteTasks(boardId: string, taskIds: string[], t: KanbanWords) {
  const done = await attempt(t("errors.deleteTasks", { count: taskIds.length }), () =>
    kanbanApi.deleteTasks(boardId, taskIds).then(() => true),
  );
  if (done) adjustTaskCount(boardId, -taskIds.length);
  return done !== null;
}

export async function saveLayout(boardId: string, layout: LayoutUpdate, t: KanbanWords) {
  return (await attempt(t("errors.saveBoard"), () => kanbanApi.saveLayout(boardId, layout).then(() => true))) !== null;
}
