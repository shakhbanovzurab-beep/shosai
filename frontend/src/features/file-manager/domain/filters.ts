import type { FileItem, FileKind } from "./contract";

export type FileShow = "all" | "starred" | "leo" | "shared";
export type FileSort = "modified" | "name" | "size";

export type FileFilter = { show: FileShow; kind: FileKind | "all"; sort: FileSort };

export const DEFAULT_FILTER: FileFilter = { show: "all", kind: "all", sort: "modified" };

/** The choices in the order the menu lists them; the UI words each one. */
export const FILE_SHOWS: readonly FileShow[] = ["all", "starred", "leo", "shared"];
export const FILE_SORTS: readonly FileSort[] = ["modified", "name", "size"];

export const isFiltered = (filter: FileFilter) => filter.show !== "all" || filter.kind !== "all";

const COMPARE: Record<FileSort, (a: FileItem, b: FileItem) => number> = {
  modified: (a, b) => b.modified_at.localeCompare(a.modified_at),
  name: (a, b) => a.name.localeCompare(b.name),
  size: (a, b) => b.size_bytes - a.size_bytes,
};

/** The files to show for a filter; `shared` holds the ids of files shared in a workspace. */
export function applyFilter(files: FileItem[], filter: FileFilter, shared: ReadonlySet<string>) {
  return files
    .filter((file) => {
      if (filter.kind !== "all" && file.kind !== filter.kind) return false;
      if (filter.show === "starred") return file.starred;
      if (filter.show === "leo") return file.leo !== null;
      if (filter.show === "shared") return shared.has(file.id);
      return true;
    })
    .toSorted(COMPARE[filter.sort]);
}
