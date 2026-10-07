import type { FileFolder } from "../domain/contract";
import { kindOf } from "../domain/files";

/*
 * The demo account's files. Research is a folder Leo reads, the roadmap and the launch plan are
 * chosen one by one, and the launch plan is also shared in the Lumen workspace (see the workspace
 * demo), so every link between files, Leo and workspaces can be tried at once. File and folder names are
 * what the user called them, so they stay as written in every interface language.
 */

export type StoredFile = {
  id: string;
  name: string;
  content_type: string;
  size_bytes: number;
  folder_id: string | null;
  modified_at: string;
  starred: boolean;
  /** The file's own "Use with Leo". */
  leo_on: boolean;
  /** When Leo started reading it; null while Leo doesn't use it. */
  index_started_at: number | null;
};

const MINUTE = 60_000;
const ago = (minutes: number) => new Date(Date.now() - minutes * MINUTE).toISOString();
const HOUR = 60;
const DAY = 24 * HOUR;
const MB = 1024 * 1024;

const CONTENT_TYPES: Record<string, string> = {
  pdf: "application/pdf",
  document: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  spreadsheet: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  text: "text/markdown", // i18n-ignore: a MIME type keyed by file kind, not copy
  archive: "application/zip",
  image: "image/svg+xml",
};

export const contentTypeOf = (name: string) => CONTENT_TYPES[kindOf(name)] ?? "application/octet-stream";

export const seedFolders = (): FileFolder[] =>
  (
    [
      ["brand-assets", "Brand assets", 12 * DAY, false],
      ["product-design", "Product design", 2 * DAY, false],
      ["legal-documents", "Legal documents", 9 * DAY, false],
      ["research", "Research", 3 * DAY, true],
      ["marketing", "Marketing", 6 * DAY, false],
      ["team-resources", "Team resources", 20 * DAY, false],
    ] as const
  ).map(([id, name, minutes, leo]) => ({ id, name, updated_at: ago(minutes), leo }));

type Seed = [id: string, name: string, bytes: number, folder: string | null, minutes: number, starred?: boolean];

const file = ([id, name, size_bytes, folder_id, minutes, starred = false]: Seed, leo_on = false): StoredFile => ({
  id,
  name,
  content_type: contentTypeOf(name),
  size_bytes: Math.round(size_bytes),
  folder_id,
  modified_at: ago(minutes),
  starred,
  leo_on,
  index_started_at: null,
});

export const seedFiles = (): StoredFile[] => [
  file(["f-roadmap", "Product roadmap 2027.pdf", 8.4 * MB, null, 5, true], true),
  file(["f-launch-plan", "Leo beta launch plan.md", 18_400, null, 3 * DAY], true),
  file(["f-budget", "Quarterly budget forecast.xlsx", 3.8 * MB, null, 2 * DAY]),
  file(["f-launch-brief", "Product launch brief.pdf", 4.2 * MB, null, 4 * DAY]),
  file(["f-release-assets", "Release assets.zip", 186 * MB, null, 8 * DAY]),
  file(["f-brand-exports", "Brand exports.zip", 72 * MB, "brand-assets", 12 * DAY]),
  file(["f-logo-kit", "Logo kit.svg", 1.1 * MB, "brand-assets", 15 * DAY]),
  file(["f-design-system", "Design system foundations.fig", 24.1 * MB, "product-design", 2 * HOUR, true]),
  file(["f-prototype", "Mobile app prototype.fig", 18.6 * MB, "product-design", 2 * DAY, true]),
  file(["f-partnership", "Partnership agreement.docx", 620_000, "legal-documents", 9 * DAY]),
  file(["f-nda", "Mutual NDA template.docx", 84_000, "legal-documents", 30 * DAY]),
  file(["f-research-notes", "Customer research notes.docx", 1.2 * MB, "research", 3 * DAY, true]),
  file(["f-northwind-notes", "Northwind interview notes.pdf", 412_000, "research", 6 * DAY]),
  file(["f-survey", "Onboarding survey results.csv", 240_000, "research", 10 * DAY]),
  file(["f-campaign", "Campaign performance.xlsx", 2.7 * MB, "marketing", DAY]),
  file(["f-handoff", "Handoff checklist.pdf", 940_000, "team-resources", 20 * DAY]),
];
