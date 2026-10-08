import type { KnowledgeAccess, KnowledgeItem, KnowledgeKind, KnowledgeSource } from "../domain/knowledge-contract";
import { connector, daysAgo, everyone, team, UPLOAD } from "./demo-knowledge";

/* The two demo workspaces' files and sources. */

type Seed = {
  id: string;
  name: string;
  kind: KnowledgeKind;
  by: string;
  days: number;
  access: KnowledgeAccess;
  size?: number;
  pages?: number;
  source?: KnowledgeSource;
  project?: string;
};

const item = (seed: Seed): KnowledgeItem => ({
  id: seed.id,
  name: seed.name,
  kind: seed.kind,
  added_by: seed.by,
  added_at: daysAgo(seed.days),
  access: seed.access,
  source: seed.source ?? UPLOAD,
  project_id: seed.project ?? null,
  status: "ready",
  size_bytes: seed.size ?? null,
  page_count: seed.pages ?? null,
});

export const lumenKnowledge = (): KnowledgeItem[] =>
  [
    {
      id: "k-handbook",
      name: "Company handbook.pdf",
      kind: "pdf",
      by: "m-arham",
      days: 120,
      access: everyone,
      size: 2_480_000,
    },
    {
      id: "k-brand",
      name: "Brand guidelines.pdf",
      kind: "pdf",
      by: "m-diego",
      days: 64,
      access: everyone,
      size: 8_900_000,
    },
    {
      id: "k-security",
      name: "Security & data handling.docx",
      kind: "doc",
      by: "m-noah",
      days: 30,
      access: everyone,
      size: 310_000,
    },
    {
      id: "k-eng",
      name: "Engineering wiki",
      kind: "notion",
      by: "m-maya",
      days: 21,
      access: team("engineering"),
      pages: 148,
      source: connector("notion", "https://notion.so/lumen/engineering"),
    },
    {
      id: "k-research",
      name: "Customer research — Q3",
      kind: "drive",
      by: "m-priya",
      days: 12,
      access: team("product"),
      pages: 36,
      source: connector("drive", "https://drive.google.com/drive/folders/research-q3"),
      project: "onboarding",
    },
    {
      id: "k-pricing",
      name: "Pricing and packaging 2026.xlsx",
      kind: "sheet",
      by: "m-elena",
      days: 4,
      access: team("sales"),
      size: 96_000,
      project: "pricing",
    },
    {
      id: "k-objections",
      name: "Sales objections playbook.docx",
      kind: "doc",
      by: "m-elena",
      days: 2,
      access: team("sales"),
      size: 180_000,
    },
    // Shared by the demo user from their File Manager: the workspace only points to it.
    {
      id: "k-pub-launch",
      name: "Leo beta launch plan.md",
      kind: "text",
      by: "m-arham",
      days: 3,
      access: team("product"),
      size: 18_400,
      source: { kind: "personal", file_id: "f-launch-plan" },
      project: "leo-beta",
    },
  ].map((seed) => item(seed as Seed));

export const northwindKnowledge = (): KnowledgeItem[] =>
  [
    {
      id: "nk-security",
      name: "Northwind security questionnaire.pdf",
      kind: "pdf",
      by: "nw-grace",
      days: 10,
      access: everyone,
      size: 640_000,
      project: "pilot",
    },
    {
      id: "nk-criteria",
      name: "Pilot success criteria.docx",
      kind: "doc",
      by: "nw-liam",
      days: 14,
      access: everyone,
      size: 120_000,
      project: "pilot",
    },
  ].map((seed) => item(seed as Seed));
