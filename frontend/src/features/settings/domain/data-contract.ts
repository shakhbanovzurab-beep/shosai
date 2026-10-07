/*
 * ---------- Your data (Privacy) ----------
 * GET /settings/data/export (archive download), GET|DELETE /settings/data/{kind}, DELETE /settings/data/{kind}/{id}
 */

export const DATA_KINDS = ["shared_chats", "shared_artifacts", "uploaded_files", "feedback"] as const;
export type DataKind = (typeof DATA_KINDS)[number];

export const isDataKind = (kind: string): kind is DataKind => (DATA_KINDS as readonly string[]).includes(kind);

/** One shared link, uploaded file or piece of feedback, shaped the same so one list can show any kind. */
export type DataItem = {
  id: string;
  title: string;
  /** A short secondary line: file size, rating and comment, where it was shared… */
  detail: string;
  created_at: string;
  /** Public link for shared chats and artifacts; null otherwise. */
  url: string | null;
};

export type DataItemsResponse = { items: DataItem[] };
