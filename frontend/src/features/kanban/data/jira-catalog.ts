import type { Column, OwnerTone, Task, TaskPriority } from "../domain/board";
import { column } from "./demo-rows";

/*
 * What the demo pretends the user's Jira site contains. A real backend reads boards, their column
 * configuration and issues through the Jira Cloud REST API with the user's Jira connection.
 */

export const JIRA_SITE = "acme.atlassian.net";

/** The issue type Jira gives an issue created from a board here: Jira's own name for it, not the app's. */
export const NEW_ISSUE_TYPE = "Task";

type DemoIssue = [key: string, summary: string, type: string, priority: TaskPriority, assignee: string | null];

export type JiraCatalogBoard = {
  board_id: number;
  name: string;
  project_key: string;
  project_name: string;
  type: "kanban" | "scrum";
  columns: Column[];
  /** Issues per column, by column id. */
  issues: Record<string, DemoIssue[]>;
};

const TONES: OwnerTone[] = ["indigo", "lime", "fuchsia", "sky", "violet", "pink"];
const toneOf = (name: string) => TONES[[...name].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % TONES.length];

export const issueToTask = ([key, summary, type, priority, assignee]: DemoIssue): Task => ({
  id: `jira-${key}`,
  title: summary,
  description: "",
  priority,
  dueDate: null,
  progress: null,
  owner: assignee ? { name: assignee, tone: toneOf(assignee) } : null,
  label: type,
  insights: [],
  jira: { key, url: `https://${JIRA_SITE}/browse/${key}`, type },
});

export const JIRA_CATALOG: JiraCatalogBoard[] = [
  {
    board_id: 12,
    name: "WEB board",
    project_key: "WEB",
    project_name: "Website",
    type: "kanban",
    columns: [
      column("jira-12-todo", "To Do", "todo"),
      column("jira-12-progress", "In Progress", "in_progress"),
      column("jira-12-review", "In Review", "in_progress"),
      column("jira-12-done", "Done", "done"),
    ],
    issues: {
      "jira-12-todo": [
        ["WEB-148", "Pricing page: annual toggle", "Story", "High", "Maya Chen"],
        ["WEB-151", "Broken link in the footer", "Bug", "Medium", null],
        ["WEB-153", "Cookie banner copy review", "Task", "Low", "Sofia Rossi"],
      ],
      "jira-12-progress": [
        ["WEB-142", "Download page for macOS and Windows", "Story", "High", "Arham Khan"],
        ["WEB-145", "Image CDN migration", "Task", "Medium", "Noah Kim"],
      ],
      "jira-12-review": [["WEB-139", "Blog: code block styles", "Story", "Medium", "Diego Alvarez"]],
      "jira-12-done": [
        ["WEB-131", "Fix layout shift on the homepage", "Bug", "High", "Noah Kim"],
        ["WEB-127", "Add Open Graph images", "Task", "Low", "Maya Chen"],
      ],
    },
  },
  {
    board_id: 7,
    name: "MOB Sprint board",
    project_key: "MOB",
    project_name: "Mobile app",
    type: "scrum",
    columns: [
      column("jira-7-todo", "To Do", "todo"),
      column("jira-7-progress", "In Progress", "in_progress"),
      column("jira-7-done", "Done", "done"),
    ],
    issues: {
      "jira-7-todo": [
        ["MOB-88", "Offline mode for notes", "Epic", "High", "Priya Nair"],
        ["MOB-91", "Crash on login with SSO", "Bug", "High", null],
      ],
      "jira-7-progress": [["MOB-85", "Push notifications for mentions", "Story", "Medium", "Elena Petrova"]],
      "jira-7-done": [["MOB-80", "Dark mode for settings", "Story", "Low", "Priya Nair"]],
    },
  },
];
