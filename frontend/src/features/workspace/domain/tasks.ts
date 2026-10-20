import { dayIn, daysBetween } from "@/i18n/calendar-days";

import type { Task, TaskStatus } from "./content-contract";

/** "Mine" is what the signed-in member owns; "Team" is everyone's, narrowed by team, project or assignee. */
export const TASK_VIEWS = ["mine", "team"] as const;
export type TaskView = (typeof TASK_VIEWS)[number];

export type TasksQuery = { view: TaskView; team: string | null; project: string | null; assignee: string | null };

const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value) ?? null;

export function parseTasksQuery(params: Record<string, string | string[] | undefined>): TasksQuery {
  const view = TASK_VIEWS.find((v) => v === first(params.view)) ?? "mine";
  return {
    view,
    team: first(params.team),
    project: first(params.project),
    assignee: view === "team" ? first(params.assignee) : null,
  };
}

/** The Tasks page's query string for a query; the defaults stay out of it. */
export function tasksSearch({ view, team, project, assignee }: TasksQuery) {
  const params = new URLSearchParams();
  if (view !== "mine") params.set("view", view);
  if (team) params.set("team", team);
  if (project) params.set("project", project);
  if (assignee && view === "team") params.set("assignee", assignee);
  const query = params.toString();
  return query ? `?${query}` : "";
}

/** "unassigned" in the assignee filter picks tasks nobody owns yet. */
export const UNASSIGNED = "unassigned";

export function filterTasks(items: Task[], query: TasksQuery, meId: string) {
  return items.filter((t) => {
    if (query.view === "mine" && t.assignee_id !== meId) return false;
    if (query.team && t.team_id !== query.team) return false;
    if (query.project && t.project_id !== query.project) return false;
    if (query.assignee === UNASSIGNED) return t.assignee_id === null;
    return !query.assignee || t.assignee_id === query.assignee;
  });
}

export const isOpen = (task: { status: TaskStatus }) => task.status !== "done";

export const DUE_GROUPS = ["overdue", "today", "week", "later", "undated"] as const;
export type DueGroup = (typeof DUE_GROUPS)[number];

/** Группа срока; дни до срока (календарного дня) считаются от сегодня в поясе кабинета `zone`. */
export function dueGroup(dueOn: string | null, now: number, zone: string): DueGroup {
  if (dueOn === null) return "undated";
  const days = daysBetween(dayIn(now, zone), dueOn);
  if (days < 0) return "overdue";
  if (days === 0) return "today";
  return days < 7 ? "week" : "later";
}

/** Open tasks by urgency, soonest first in each group; done ones apart, most recent first. */
export function groupTasks<T extends Task>(items: T[], now: number, zone: string) {
  const open: Record<DueGroup, T[]> = { overdue: [], today: [], week: [], later: [], undated: [] };
  const done: T[] = [];
  for (const item of items) {
    if (isOpen(item)) open[dueGroup(item.due_on, now, zone)].push(item);
    else done.push(item);
  }
  const byDue = (a: T, b: T) => (a.due_on ?? "").localeCompare(b.due_on ?? "");
  for (const group of DUE_GROUPS) open[group].sort(byDue);
  done.sort((a, b) => b.created_at.localeCompare(a.created_at));
  return { groups: DUE_GROUPS.map((key) => ({ key, items: open[key] })).filter((g) => g.items.length > 0), done };
}

/** Open tasks of one assignee, overdue first. */
export function openFor<T extends Task>(items: T[], assigneeId: string, now: number, zone: string) {
  const { groups } = groupTasks(
    items.filter((t) => t.assignee_id === assigneeId),
    now,
    zone,
  );
  return groups.flatMap((g) => g.items);
}

/** Done out of all, for a project's progress. */
export function progressOf(items: Task[]) {
  const done = items.filter((t) => t.status === "done").length;
  return { done, total: items.length, percent: items.length === 0 ? 0 : Math.round((done / items.length) * 100) };
}
