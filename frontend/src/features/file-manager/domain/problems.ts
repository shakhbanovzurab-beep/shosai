import { ApiError } from "@/lib/api/errors";

/**
 * Why the files API refused a request: the error codes of the backend's `files` slice (ADR 0008). The UI words
 * them in the user's language; any other code keeps the server's text and the request id for support.
 */
export const FILE_PROBLEMS = [
  "file_not_found",
  "folder_not_found",
  "upload_count",
  "upload_not_claimable",
  "upload_too_large",
  "upload_incomplete",
  "upload_closed",
  "upload_not_found",
  "filename_invalid",
  "storage_limit",
  "storage_not_included",
  "leo_limit",
  "leo_unreadable",
  "leo_not_used",
  "entitlements_unavailable",
  "name_required",
  "name_too_long",
  "name_slash",
  "name_control_character",
] as const;

export type FileProblem = (typeof FILE_PROBLEMS)[number];

/** The known problem behind an error, with the bytes it names (the plan's limit), or null for anything else. */
export function fileProblemOf(error: unknown): { code: FileProblem; limitBytes: number | null } | null {
  if (!(error instanceof ApiError)) return null;
  const code = FILE_PROBLEMS.find((problem) => problem === error.code);
  if (code === undefined) return null;
  const limit = error.params.limit_bytes;
  return { code, limitBytes: typeof limit === "number" ? limit : null };
}
