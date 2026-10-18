import { type FileFolder, type FileItem, type FileKind, LEO_MAX_FILE_BYTES } from "./contract";

export type FileManagerView = "grid" | "list";

const KIND_BY_EXTENSION: Record<string, FileKind> = {
  pdf: "pdf",
  doc: "document",
  docx: "document",
  xls: "spreadsheet",
  xlsx: "spreadsheet",
  csv: "spreadsheet",
  ppt: "presentation",
  pptx: "presentation",
  md: "text",
  txt: "text",
  html: "text",
  json: "text",
  fig: "design",
  sketch: "design",
  png: "image",
  jpg: "image",
  jpeg: "image",
  svg: "image",
  zip: "archive",
  rar: "archive",
};

/** ".FIG" for "Prototype.fig"; empty without an extension. */
export const extensionOf = (name: string) => {
  const dot = name.lastIndexOf(".");
  return dot > 0 ? name.slice(dot + 1).toLowerCase() : "";
};

export const kindOf = (name: string): FileKind => KIND_BY_EXTENSION[extensionOf(name)] ?? "other";

/** Why Leo can't use a file, as a code the UI words: too large, an extension it can't read, or no extension. */
export type LeoBlocker =
  | { reason: "tooLarge"; maxBytes: number }
  | { reason: "extension"; extension: string }
  | { reason: "unknownType" };

/** Why Leo can't use a file, or null when it can. */
export function leoBlocker(file: Pick<FileItem, "name" | "size_bytes" | "leo_readable">): LeoBlocker | null {
  if (file.leo_readable) return null;
  if (file.size_bytes > LEO_MAX_FILE_BYTES) return { reason: "tooLarge", maxBytes: LEO_MAX_FILE_BYTES };
  const extension = extensionOf(file.name);
  return extension ? { reason: "extension", extension } : { reason: "unknownType" };
}

/**
 * Whether Leo stopped reading the file on day 90 over the plan's knowledge limit (FL-D10): Leo could read it and
 * its folder is used, yet the file isn't. Only switching the file on brings it back, within the limit.
 */
export const isHeld = (file: FileItem, folders: readonly FileFolder[]) =>
  file.leo === null &&
  file.leo_readable &&
  file.folder_id !== null &&
  folders.some((folder) => folder.id === file.folder_id && folder.leo);

/** What a folder holds right now: how many files, how big, and when one last changed. */
export function folderStats(folder: FileFolder, files: FileItem[]) {
  let count = 0;
  let bytes = 0;
  let updated = folder.updated_at;
  for (const file of files) {
    if (file.folder_id !== folder.id) continue;
    count++;
    bytes += file.size_bytes;
    if (file.modified_at > updated) updated = file.modified_at;
  }
  return { count, bytes, updated };
}

/** "Report.pdf" → "Report copy.pdf": `copyOf` words the base name ("Report" → "Report copy"), the extension stays. */
export const copyName = (name: string, copyOf: (base: string) => string) => {
  const dot = name.lastIndexOf(".");
  return dot > 0 ? `${copyOf(name.slice(0, dot))}${name.slice(dot)}` : copyOf(name);
};
