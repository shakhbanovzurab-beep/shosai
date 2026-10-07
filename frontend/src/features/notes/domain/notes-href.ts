export type NotesView = "timeline" | "grid" | "list";

export function parseNotesView(value: unknown): NotesView {
  return value === "grid" || value === "list" ? value : "timeline";
}

/** Builds a Notes library URL that keeps the folder filter and the chosen layout together. */
export function buildNotesHref({ folder, view }: { folder?: string; view: NotesView }) {
  const params = new URLSearchParams();
  if (folder) params.set("folder", folder);
  if (view !== "timeline") params.set("view", view);
  const query = params.toString();
  return query ? `/app/notes?${query}` : "/app/notes";
}
