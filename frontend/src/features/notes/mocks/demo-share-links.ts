import {
  expiryDate,
  isExpired,
  type SharedComment,
  type ShareLink,
  type ShareLinkSettings,
} from "../domain/share-link";

// 12 случайных байт в base64url, как у токенов ссылок бэкенда.
const randomToken = () =>
  btoa(String.fromCharCode(...crypto.getRandomValues(new Uint8Array(12))))
    .replaceAll("+", "-")
    .replaceAll("/", "_")
    .replaceAll("=", "");

// In-memory stand-in for the backend's share links; on globalThis so every module shares it.
interface Store {
  /** The one link of each meeting, by note id. */
  links: Map<string, ShareLink>;
  /** Which meeting a token opens. */
  notesByToken: Map<string, string>;
  comments: Map<string, SharedComment[]>;
}
const shared = globalThis as typeof globalThis & { notesDemoShareLinks?: Store };
shared.notesDemoShareLinks ??= { links: new Map(), notesByToken: new Map(), comments: new Map() };
const store = shared.notesDemoShareLinks;

export const getShareLink = (noteId: string): ShareLink | null => store.links.get(noteId) ?? null;

/**
 * Creates the meeting's link, or changes what it shows. A new expiry counts from now; the token stays,
 * so a link already sent keeps working.
 */
export function saveShareLink(noteId: string, settings: ShareLinkSettings): ShareLink {
  const current = store.links.get(noteId);
  const token = current?.token ?? randomToken();
  const sameExpiry = current?.settings.expiry === settings.expiry;
  const expiresAt = current && sameExpiry ? current.expiresAt : expiryDate(settings.expiry, new Date());
  const link: ShareLink = { token, settings, expiresAt };
  store.links.set(noteId, link);
  store.notesByToken.set(token, noteId);
  return link;
}

/** Stops the link working; turning sharing back on makes a new one. */
export function revokeShareLink(noteId: string) {
  const current = store.links.get(noteId);
  if (!current) return;
  store.links.delete(noteId);
  store.notesByToken.delete(current.token);
  store.comments.delete(current.token);
}

/** The meeting and link a token opens, while the link works. */
export function openShareLink(token: string): { noteId: string; link: ShareLink } | null {
  const noteId = store.notesByToken.get(token);
  const link = noteId ? store.links.get(noteId) : undefined;
  if (!noteId || !link || isExpired(link, new Date())) return null;
  return { noteId, link };
}

export const listComments = (token: string): SharedComment[] => store.comments.get(token) ?? [];

export function addComment(token: string, author: string, text: string): SharedComment {
  const comment: SharedComment = { id: crypto.randomUUID(), author, text, createdAt: new Date().toISOString() };
  store.comments.set(token, [...listComments(token), comment]);
  return comment;
}
