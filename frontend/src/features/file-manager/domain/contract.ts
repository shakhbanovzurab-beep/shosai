/**
 * File Manager API contract: the account's own files, the one place they are stored. The route
 * handlers in `server/` (mounted under `src/app/api/files`) forward to `${BACKEND_API_URL}/v1/files/*`
 * and fall back to an in-memory demo. Field names are snake_case; errors are `{ "detail": string }`.
 * See docs/file-manager-api.md.
 *
 * GET    /files                 → FilesResponse
 * POST   /files                 → 201 UploadResponse   (multipart: `files`, optional `folder_id`, `leo` = "true")
 * PATCH  /files/{id}            → FileItem             (FileUpdate)
 * DELETE /files/{id}            → 204                  (also leaves every workspace it is shared in)
 * POST   /files/{id}/copy       → 201 FileItem
 * POST   /files/{id}/reindex    → FileItem             (Leo reads it again)
 * POST   /files/{id}/transfer   → 204                  (TransferRequest: the workspace takes it over)
 * POST   /files/folders         → 201 FileFolder       ({name})
 * PATCH  /files/folders/{id}    → FileFolder           (FolderUpdate)
 * DELETE /files/folders/{id}    → 204                  (its files move to My files)
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
export type UploadResponse = { files: FileItem[] };

/** `leo` is the file's own choice; a file in a folder Leo reads is used either way. */
export type FileUpdate = { name?: string; folder_id?: string | null; starred?: boolean; leo?: boolean };
export type FolderUpdate = { name?: string; leo?: boolean };

/** Hands a file shared in a workspace over to it: it stays there for good and leaves My files. */
export type TransferRequest = { workspace_id: string };

export const NAME_MAX = 120;
export const MAX_FILES_PER_UPLOAD = 20;
export const MAX_UPLOAD_BYTES = 2 * 1024 ** 3;

/** What Leo reads: these types, up to 50 MB each. */
export const LEO_EXTENSIONS = [".pdf", ".docx", ".pptx", ".xlsx", ".csv", ".txt", ".md", ".html", ".json"] as const;
export const LEO_MAX_FILE_BYTES = 50 * 1024 ** 2;

export const isLeoReadable = (name: string, size: number) =>
  size <= LEO_MAX_FILE_BYTES && LEO_EXTENSIONS.some((ext) => name.toLowerCase().endsWith(ext));

export const IN_PROGRESS: ReadonlySet<IndexStatus> = new Set(["queued", "parsing", "chunking", "embedding"]);
