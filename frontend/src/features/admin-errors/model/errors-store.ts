"use client";

import { toast } from "sonner";

import { errorMessage } from "@/lib/errors";
import { createPollingResource, type PollingResource } from "@/lib/polling-resource";

import { errorsApi } from "../api/errors-api";
import type { IssueDetail, IssuesResponse, UpdateIssueRequest } from "../domain/contract";
import { type IssuesQuery, issuesQueryToParams } from "../domain/query";

const MAX_CACHED_LISTS = 12;

/** One resource per list query string, so going back to a filter shows its data at once. */
const listResources = new Map<string, PollingResource<IssuesResponse>>();
const detailResources = new Map<string, PollingResource<IssueDetail>>();

/** The list query string last shown, for the detail page's way back. */
let lastListSearch = "";
export const getLastListSearch = () => lastListSearch;

export function issuesResource(query: IssuesQuery): PollingResource<IssuesResponse> {
  const search = issuesQueryToParams(query).toString();
  let resource = listResources.get(search);
  if (!resource) {
    const base = createPollingResource(() => errorsApi.list(search));
    resource = {
      ...base,
      // Remembered when the list is on screen, not while rendering.
      subscribe: (listener) => {
        lastListSearch = search;
        return base.subscribe(listener);
      },
    };
    listResources.set(search, resource);
    const oldest = listResources.keys().next().value;
    if (listResources.size > MAX_CACHED_LISTS && oldest !== undefined) listResources.delete(oldest);
  }
  return resource;
}

export function issueResource(id: string): PollingResource<IssueDetail> {
  let resource = detailResources.get(id);
  if (!resource) {
    resource = createPollingResource(() => errorsApi.get(id));
    detailResources.set(id, resource);
  }
  return resource;
}

/** Copies the issue's new status and assignee into every cached list that shows it. */
function syncLists(issue: IssueDetail) {
  for (const resource of listResources.values()) {
    resource.update((data) =>
      data.items.some((item) => item.id === issue.id)
        ? {
            ...data,
            items: data.items.map((item) =>
              item.id === issue.id ? { ...item, status: issue.status, assignee: issue.assignee } : item,
            ),
          }
        : data,
    );
  }
}

/** Changes status or assignee right away and rolls back if the server refuses. */
export async function updateIssue(id: string, patch: UpdateIssueRequest) {
  const resource = issueResource(id);
  const before = resource.getSnapshot();
  resource.update((issue) => ({
    ...issue,
    status: patch.status ?? issue.status,
    assignee:
      patch.assignee === undefined
        ? issue.assignee
        : (issue.assignees.find((assignee) => assignee.id === patch.assignee) ?? null),
  }));
  try {
    const saved = await errorsApi.update(id, patch);
    resource.update(() => saved);
    syncLists(saved);
    return saved;
  } catch (error) {
    if (before.status === "ready") resource.update(() => before.data);
    toast.error("Не удалось сохранить", { description: errorMessage(error) });
    throw error;
  }
}
