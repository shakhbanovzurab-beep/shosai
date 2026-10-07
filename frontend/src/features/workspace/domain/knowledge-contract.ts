/**
 * What a workspace knows besides its meetings: files and sources, who owns each and who Leo answers
 * from it for. The routes are listed in `content-contract.ts`. See docs/workspace-api.md.
 */

export const CONNECTOR_PROVIDERS = ["drive", "notion", "confluence", "web"] as const;
export type ConnectorProvider = (typeof CONNECTOR_PROVIDERS)[number];

export const KNOWLEDGE_KINDS = ["pdf", "doc", "sheet", "slides", "text", ...CONNECTOR_PROVIDERS] as const;
export type KnowledgeKind = (typeof KNOWLEDGE_KINDS)[number];

/** Knowledge is for a team or for everyone; Leo answers from it for whoever can see it. */
export type KnowledgeAccess = { level: "team" | "workspace"; team_id: string | null };

/**
 * Where a piece of knowledge comes from, which decides who owns it:
 * - `upload`: a file that belongs to the workspace; it stays when whoever added it leaves.
 * - `personal`: a member's own file, shared from their File Manager. The workspace points to it; it
 *   leaves with its owner, and they can hand it over to the workspace (it becomes an upload).
 * - `connector`: a source the workspace connected, kept in sync.
 */
export type KnowledgeSource =
  | { kind: "upload" }
  | { kind: "personal"; file_id: string }
  | { kind: "connector"; provider: ConnectorProvider; url: string | null };

export type KnowledgeItem = {
  id: string;
  name: string;
  kind: KnowledgeKind;
  added_by: string;
  added_at: string;
  access: KnowledgeAccess;
  source: KnowledgeSource;
  /** The project it belongs to; shown on the project's page too. */
  project_id: string | null;
  status: "indexing" | "ready" | "failed";
  /** Bytes for a file; null for a connected source. */
  size_bytes: number | null;
  /** Pages synced from a connected source; null for a file. */
  page_count: number | null;
};

export type KnowledgeResponse = { items: KnowledgeItem[] };

export type KnowledgeUpdate = { access?: KnowledgeAccess; project_id?: string | null };

export type ShareFileRequest = {
  file_id: string;
  name: string;
  size_bytes: number;
  content_type: string;
  access: KnowledgeAccess;
  project_id: string | null;
};

export type ConnectSourceRequest = {
  provider: ConnectorProvider;
  name: string;
  url: string | null;
  access: KnowledgeAccess;
};

export const KNOWLEDGE_FILES_PER_UPLOAD = 10;
export const KNOWLEDGE_FILE_MAX_BYTES = 25 * 1024 * 1024;
