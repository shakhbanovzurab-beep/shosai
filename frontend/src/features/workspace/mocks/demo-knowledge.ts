import type {
  ConnectorProvider,
  ConnectSourceRequest,
  KnowledgeAccess,
  KnowledgeItem,
  KnowledgeKind,
  KnowledgeSource,
  ShareFileRequest,
} from "../domain/knowledge-contract";

/* Workspace knowledge for the demo; new files and sources "index" for a few seconds, then are ready. */

const INDEXING_MS = 4000;
export const everyone: KnowledgeAccess = { level: "workspace", team_id: null };
export const team = (team_id: string): KnowledgeAccess => ({ level: "team", team_id });
export const daysAgo = (days: number) => new Date(Date.now() - days * 86_400_000).toISOString();
export const UPLOAD: KnowledgeSource = { kind: "upload" };
export const connector = (provider: ConnectorProvider, url: string): KnowledgeSource => ({
  kind: "connector",
  provider,
  url,
});

const KIND_BY_EXTENSION: Record<string, KnowledgeKind> = {
  pdf: "pdf",
  doc: "doc",
  docx: "doc",
  md: "text",
  txt: "text",
  html: "text",
  json: "text",
  xls: "sheet",
  xlsx: "sheet",
  csv: "sheet",
  ppt: "slides",
  pptx: "slides",
};

export const kindOf = (fileName: string): KnowledgeKind =>
  KIND_BY_EXTENSION[fileName.split(".").at(-1)?.toLowerCase() ?? ""] ?? "text";

const fresh = (fields: Pick<KnowledgeItem, "name" | "kind" | "access" | "source" | "project_id">, by: string) =>
  ({
    id: `k-${crypto.randomUUID().slice(0, 8)}`,
    added_by: by,
    added_at: new Date().toISOString(),
    status: "indexing",
    size_bytes: null,
    page_count: null,
    ...fields,
  }) satisfies KnowledgeItem;

/** A file uploaded to the workspace, indexing until `INDEXING_MS` have passed. */
export const uploadedItem = (file: File, by: string, access: KnowledgeAccess, project_id: string | null) => ({
  ...fresh({ name: file.name, kind: kindOf(file.name), access, source: UPLOAD, project_id }, by),
  size_bytes: file.size,
});

/** One of a member's files, shared here: the workspace answers from the owner's index. */
export const sharedFileItem = (request: ShareFileRequest, by: string) => ({
  ...fresh(
    {
      name: request.name,
      kind: kindOf(request.name),
      access: request.access,
      source: { kind: "personal", file_id: request.file_id },
      project_id: request.project_id,
    },
    by,
  ),
  size_bytes: request.size_bytes,
});

/** A source the workspace connected; its pages show up once the first sync finishes. */
export const connectedItem = (request: ConnectSourceRequest, by: string) =>
  fresh(
    {
      name: request.name,
      kind: request.provider,
      access: request.access,
      source: { kind: "connector", provider: request.provider, url: request.url },
      project_id: null,
    },
    by,
  );

/** Finishes indexing of new items old enough; called on every read. A synced source gets its pages. */
export function advanceIndexing(items: KnowledgeItem[]) {
  const now = Date.now();
  for (const entry of items) {
    if (entry.status !== "indexing" || now - Date.parse(entry.added_at) < INDEXING_MS) continue;
    entry.status = "ready";
    if (entry.source.kind === "connector") entry.page_count = 12 + (entry.name.length % 30);
  }
}
