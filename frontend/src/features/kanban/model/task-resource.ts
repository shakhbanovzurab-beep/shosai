"use client";

import { usePollingResource } from "@/hooks/use-polling-resource";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { tasksApi } from "../api/tasks-api";
import type { TaskDetail } from "../domain/tasks-contract";

/* Задача целиком для панели: поля, описание, подзадачи, вложения, источник. Читается при открытии панели. */

const details = new Map<string, PollingResource<TaskDetail>>();

export function taskResource(id: string) {
  const existing = details.get(id);
  if (existing) return existing;
  const created = createPollingResource(() => tasksApi.get(id));
  details.set(id, created);
  return created;
}

export const useTaskDetail = (id: string) => usePollingResource(taskResource(id));
