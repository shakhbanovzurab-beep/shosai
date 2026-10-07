import type { Task } from "../domain/board";
import { demoTask } from "./demo-rows";
import { taskOwners } from "./task-owners";

/* The Work board's Building, QA and Shipped columns. */

export const buildingTasks: Task[] = [
  demoTask(
    "sqlite-drizzle-schema",
    "SQLite and Drizzle schema",
    "Model parties, employees, tenders, work orders, salary imports, and documents.",
    {
      priority: "High",
      due: "2026-06-26",
      progress: 65,
      owner: taskOwners.arham,
      team: "Data",
      insights: { attachments: 5, comments: 11, documents: 4 },
    },
  ),
  demoTask(
    "salary-excel-import",
    "Salary Excel import",
    "Read salary sheets with SheetJS and persist import batches locally.",
    {
      priority: "High",
      due: "2026-06-28",
      progress: 45,
      owner: taskOwners.junaid,
      team: "Data",
      insights: { attachments: 3, comments: 8, documents: 2 },
    },
  ),
  demoTask(
    "column-mapping-builder",
    "Column mapping builder",
    "Map Excel columns to salary fields with reusable templates per party.",
    {
      priority: "Medium",
      due: "2026-07-01",
      progress: 30,
      owner: taskOwners.sara,
      team: "Design",
      insights: { comments: 6, documents: 2 },
    },
  ),
];

export const qaTasks: Task[] = [
  demoTask(
    "salary-row-validation",
    "Salary row validation",
    "Flag missing employee IDs, invalid amounts, duplicate rows, and unmapped fields.",
    {
      priority: "High",
      due: "2026-07-04",
      progress: 75,
      owner: taskOwners.nisha,
      team: "QA",
      insights: { attachments: 4, comments: 10 },
    },
  ),
  demoTask(
    "payslip-preview",
    "Payslip preview",
    "Preview generated payslips before bulk PDF export and document history.",
    {
      priority: "Medium",
      due: "2026-07-06",
      progress: 60,
      owner: taskOwners.junaid,
      team: "Finance Ops",
      insights: { attachments: 3, comments: 7, documents: 3 },
    },
  ),
];

export const shippedTasks: Task[] = [
  demoTask(
    "architecture-rule",
    "Architecture rule locked",
    "Renderer stays UI-only; preload, IPC, services, and database stay separated.",
    {
      priority: "High",
      due: "2026-06-08",
      progress: 100,
      owner: taskOwners.arham,
      team: "Backend",
      insights: { comments: 6, documents: 3 },
    },
  ),
  demoTask(
    "private-mvp-scope",
    "Private MVP scope",
    "Start private source first, then revisit open-core after workflow validation.",
    {
      priority: "Medium",
      due: "2026-06-10",
      progress: 100,
      owner: taskOwners.rahul,
      team: "Finance Ops",
      insights: { attachments: 2, comments: 4 },
    },
  ),
  demoTask(
    "mvp-module-priorities",
    "MVP module priorities",
    "Payslip generation is first, but data model supports wider tender operations.",
    {
      priority: "Medium",
      due: "2026-06-12",
      progress: 100,
      owner: taskOwners.meera,
      team: "Finance Ops",
      insights: { comments: 5, documents: 2 },
    },
  ),
];
