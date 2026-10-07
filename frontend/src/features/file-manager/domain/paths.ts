import type { FileManagerView } from "./files";

const ROOT = "/app/file-manager";

const withView = (path: string, view?: FileManagerView | null) => (view === "list" ? `${path}?view=list` : path);

export const rootHref = (view?: FileManagerView | null) => withView(ROOT, view);

export const folderHref = (folderId: string, view?: FileManagerView | null) =>
  withView(`${ROOT}/folders/${encodeURIComponent(folderId)}`, view);
