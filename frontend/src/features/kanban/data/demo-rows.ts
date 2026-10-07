import type { Column, ColumnKind, Task, TaskInsightLabel, TaskOwnerProfile, TaskPriority } from "../domain/board";

/*
 * Builders for the demo boards' rows. Column names, task titles, descriptions and teams are what a user
 * wrote on their own boards, so they stay as written in every interface language.
 */

export const column = (id: string, title: string, kind: ColumnKind): Column => ({ id, title, kind });

const INSIGHTS = { attachments: "Attachments", comments: "Comments", documents: "Documents" } as const satisfies Record<
  string,
  TaskInsightLabel
>;
type InsightKind = keyof typeof INSIGHTS;
const INSIGHT_KINDS = Object.keys(INSIGHTS) as InsightKind[];

type DemoTaskFields = {
  priority?: TaskPriority;
  /** A calendar day, "2026-06-26". */
  due?: string;
  /** 0–100 while the work is tracked. */
  progress?: number;
  owner?: TaskOwnerProfile | null;
  /** The team or area the user tagged it with. */
  team?: string;
  insights?: Partial<Record<InsightKind, number>>;
};

/** A demo task: its id, title and description (may be empty), then whatever else it has. */
export function demoTask(id: string, title: string, description: string, fields: DemoTaskFields = {}): Task {
  const { priority = "Medium", due = null, progress = null, owner = null, team = null, insights = {} } = fields;
  return {
    id,
    title,
    description,
    priority,
    dueDate: due,
    progress,
    owner,
    label: team,
    insights: INSIGHT_KINDS.flatMap((kind) => {
      const count = insights[kind];
      return count === undefined ? [] : [{ label: INSIGHTS[kind], count }];
    }),
  };
}
