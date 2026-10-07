import type { Task } from "../domain/board";
import { demoTask } from "./demo-rows";
import { taskOwners } from "./task-owners";

/* The Work board's Ideas and Planned columns. */

export const ideaTasks: Task[] = [
  demoTask(
    "tender-workflow-map",
    "Tender workflow map",
    "Model Tender, Award/L1, Work Order, allocation, salary, and documents.",
    {
      priority: "High",
      due: "2026-06-14",
      progress: 10,
      owner: taskOwners.arham,
      team: "Product",
      insights: { comments: 7, documents: 3 },
    },
  ),
  demoTask(
    "license-strategy-research",
    "License strategy research",
    "Compare private MVP, open core, GPL, AGPL, and commercial modules.",
    {
      priority: "Medium",
      due: "2026-06-16",
      progress: 20,
      owner: taskOwners.rahul,
      team: "Finance Ops",
      insights: { attachments: 2, comments: 5 },
    },
  ),
  demoTask(
    "backup-restore-plan",
    "Backup and restore plan",
    "Define local database backup, restore, and exported document recovery.",
    {
      priority: "Medium",
      due: "2026-06-18",
      progress: 15,
      owner: taskOwners.maya,
      team: "Platform",
      insights: { attachments: 1, comments: 4 },
    },
  ),
  demoTask(
    "work-order-allocation-model",
    "Work order allocation model",
    "Sketch how awarded work orders connect to employee allocations and salary months.",
    {
      priority: "Medium",
      due: "2026-06-19",
      progress: 5,
      owner: taskOwners.meera,
      team: "Product",
      insights: { comments: 3, documents: 1 },
    },
  ),
  demoTask(
    "future-sync-notes",
    "Future sync notes",
    "Capture local-first sync assumptions before deciding on cloud PostgreSQL and file storage.",
    {
      priority: "Low",
      due: "2026-06-21",
      progress: 0,
      owner: taskOwners.arham,
      team: "Platform",
      insights: { comments: 2 },
    },
  ),
];

export const plannedTasks: Task[] = [
  demoTask(
    "electron-app-shell",
    "Electron app shell",
    "Create local-first desktop shell with React, Tailwind, and shadcn/ui.",
    {
      priority: "High",
      due: "2026-06-20",
      progress: 25,
      owner: taskOwners.arham,
      team: "Platform",
      insights: { attachments: 4, comments: 9, documents: 2 },
    },
  ),
  demoTask(
    "secure-preload-api",
    "Secure preload API",
    "Expose renderer-safe methods for imports, records, PDFs, and backups.",
    {
      priority: "High",
      due: "2026-06-22",
      progress: 20,
      owner: taskOwners.nisha,
      team: "Backend",
      insights: { attachments: 2, comments: 6, documents: 1 },
    },
  ),
  demoTask(
    "party-employee-records",
    "Party and employee records",
    "Create local records for clients, contractors, employees, and identifiers.",
    {
      priority: "Medium",
      due: "2026-06-24",
      progress: 15,
      owner: taskOwners.meera,
      team: "Product",
      insights: { comments: 5, documents: 2 },
    },
  ),
  demoTask(
    "generated-documents-index",
    "Generated documents index",
    "Plan filters for generated PDFs by party, salary month, employee, and import batch.",
    {
      priority: "Medium",
      due: "2026-06-25",
      progress: 10,
      owner: taskOwners.maya,
      team: "Docs",
      insights: { attachments: 2, comments: 4 },
    },
  ),
];
