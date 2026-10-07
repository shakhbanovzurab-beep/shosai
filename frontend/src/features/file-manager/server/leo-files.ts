import { present, store } from "./demo-store";

/** The account's files Leo has read, and the ones whose names match a question. */
export type LeoFiles = { usable: { id: string; name: string }[]; matched: { id: string; name: string }[] };

const words = (text: string) => text.toLowerCase().match(/[a-z0-9]{4,}/g) ?? [];

/** What Leo may read from the account's own files in Personal: only files it uses and has indexed. */
export function leoFiles(question: string): LeoFiles {
  const now = Date.now();
  const usable = store.files
    .map((f) => present(f, now))
    .filter((f) => f.leo?.status === "indexed")
    .map(({ id, name }) => ({ id, name }));
  const asked = new Set(words(question));
  return { usable, matched: usable.filter((f) => words(f.name).some((w) => asked.has(w))) };
}
