/**
 * File Manager API contract: the account's own files, the one place they are stored, on the backend's
 * `/v1/files*` and `/v1/me/uploads*` (files slice). These are the shapes the slice uses; `contract.test.ts`
 * holds them equal to the generated OpenAPI schema. See docs/file-manager-api.md.
 */

export const FILE_KINDS = [
  "document",
  "spreadsheet",
  "presentation",
  "pdf",
  "text",
  "design",
  "image",
  "archive",
  "other",
] as const;
export type FileKind = (typeof FILE_KINDS)[number];

/** queued → parsing → chunking → embedding → indexed, or failed at any step. */
export type IndexStatus = "queued" | "parsing" | "chunking" | "embedding" | "indexed" | "failed";

/**
 * How Leo uses a file: chosen on the file itself, or through its folder. Leo reads it for the
 * account in Personal; a workspace it is shared in answers from the same index.
 */
export type LeoUse = {
  via: "file" | "folder";
  status: IndexStatus;
  /** 0–100 within the current step; 100 once indexed. */
  progress: number;
  /** Chunks in the vector index; null until chunking finishes. */
  chunk_count: number | null;
  error: string | null;
};

export type FileItem = {
  id: string;
  name: string;
  kind: FileKind;
  content_type: string;
  size_bytes: number;
  /** Null: in My files, outside any folder. */
  folder_id: string | null;
  modified_at: string;
  starred: boolean;
  /** Whether Leo can read it at all: a supported type, up to `LEO_MAX_FILE_BYTES`. */
  leo_readable: boolean;
  /** Null while Leo doesn't use it. */
  leo: LeoUse | null;
};

export type FileFolder = {
  id: string;
  name: string;
  updated_at: string;
  /** Leo uses every readable file in it, including files added later. */
  leo: boolean;
};

export type FilesResponse = { folders: FileFolder[]; files: FileItem[] };

/**
 * The person's storage and Leo's bytes against the plan (`GET /v1/files/storage`). A null limit is unlimited;
 * the dates are set only over a limit: storage's 90 days (FL-D2) and Leo's (FL-D10).
 */
export type StorageStanding = {
  used_bytes: number;
  limit_bytes: number | null;
  over_limit_since: string | null;
  removal_at: string | null;
  leo_used_bytes: number;
  leo_limit_bytes: number | null;
  leo_over_limit_since: string | null;
  leo_removal_at: string | null;
};
export type UploadResponse = { files: FileItem[] };

/** `leo` is the file's own choice; a file in a folder Leo reads is used either way. */
export type FileUpdate = { name?: string; folder_id?: string | null; starred?: boolean; leo?: boolean };
export type FolderUpdate = { name?: string; leo?: boolean };

export const NAME_MAX = 120;
export const MAX_FILES_PER_UPLOAD = 20;
export const MAX_UPLOAD_BYTES = 2 * 1024 ** 3;

/** What Leo reads: these types, up to 50 MB each. */
export const LEO_EXTENSIONS = [".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".txt", ".md", ".html", ".json"] as const;
export const LEO_MAX_FILE_BYTES = 50 * 1024 ** 2;

export const isLeoReadable = (name: string, size: number) =>
  size <= LEO_MAX_FILE_BYTES && LEO_EXTENSIONS.some((ext) => name.toLowerCase().endsWith(ext));

export const IN_PROGRESS: ReadonlySet<IndexStatus> = new Set(["queued", "parsing", "chunking", "embedding"]);
/** The steps knowledge is working through now; a queued file only waits for it. */
export const INDEXING: ReadonlySet<IndexStatus> = new Set(["parsing", "chunking", "embedding"]);
