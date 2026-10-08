import type { DataItem, DataKind } from "../domain/data-contract";

/*
 * In-memory samples for Privacy › Your data, used when BACKEND_API_URL is unset; reset on restart. The
 * backend writes each row's title and detail, so the demo rows stay as written in every interface language.
 */

const daysAgo = (days: number) => new Date(Date.now() - days * 86400000).toISOString();
const share = (id: string) => `https://leo.example/share/${id}`;

/** A row as the backend sends it, already written: a chat's title, a file's name and type, a rating and comment. */
const row = (id: string, title: string, detail: string, days: number, url: string | null = null): DataItem => ({
  id,
  title,
  detail,
  created_at: daysAgo(days),
  url,
});

const shared = globalThis as typeof globalThis & { settingsDemoData?: Record<DataKind, DataItem[]> };
shared.settingsDemoData ??= {
  shared_chats: [
    row("sc1", "System design: URL shortener", "Anyone with the link", 3, share("sc1")),
    row("sc2", "FastAPI background tasks", "Anyone with the link", 12, share("sc2")),
  ],
  shared_artifacts: [row("sa1", "Interview prep checklist", "Document", 5, share("sa1"))],
  uploaded_files: [
    row("uf1", "resume-2026.pdf", "PDF · 184 KB", 2),
    row("uf2", "architecture-diagram.png", "Image · 1.2 MB", 9),
    row("uf3", "meeting-notes.md", "Markdown · 6 KB", 21),
  ],
  feedback: [
    row("fb1", "Good answer", "“Clear trade-offs, exactly what I needed.”", 1),
    row("fb2", "Bad answer", "“Code didn’t compile.”", 8),
  ],
};
const store = shared.settingsDemoData;

export const listItems = (kind: DataKind) => store[kind];

export function deleteItem(kind: DataKind, id: string): boolean {
  const before = store[kind].length;
  store[kind] = store[kind].filter((item) => item.id !== id);
  return store[kind].length < before;
}

export function deleteAll(kind: DataKind) {
  store[kind] = [];
}
