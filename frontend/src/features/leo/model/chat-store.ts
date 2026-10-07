import { finishMessage } from "../domain/messages";
import type { LeoMessage } from "../domain/types";

/* Leo's conversations, one per context (Personal, each workspace), kept outside React and in localStorage. */

const MAX_STORED_MESSAGES = 50;
const EMPTY_MESSAGES: LeoMessage[] = [];

/** Personal keeps the original key, so an existing conversation survives the move to contexts. */
const storageKey = (key: string) => (key === "personal" ? "leo-chat" : `leo-chat:${key}`);

let idCounter = 0;
export const createId = () => `${Date.now().toString(36)}-${(idCounter++).toString(36)}`;

function loadMessages(key: string): LeoMessage[] {
  try {
    const raw = window.localStorage.getItem(storageKey(key));
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    // A reply that was still streaming when the page closed can never finish.
    return (parsed as LeoMessage[]).map((m) => (m.status === "streaming" ? finishMessage(m, "stopped") : m));
  } catch {
    return [];
  }
}

function saveMessages(key: string, messages: LeoMessage[]) {
  try {
    window.localStorage.setItem(storageKey(key), JSON.stringify(messages.slice(-MAX_STORED_MESSAGES)));
  } catch {
    // Storage can be unavailable (private mode, quota); the chat still works without it.
  }
}

// File contents stay in memory for this page session only, keyed by message id, so "Regenerate"
// can send them again. After a reload only the attachment metadata remains.
export const attachmentFiles = new Map<string, File[]>();

// Read from storage lazily on the client while the server (and hydration) render an empty history.
const conversations = new Map<string, LeoMessage[]>();
const listeners = new Set<() => void>();

export function getMessages(key: string) {
  let messages = conversations.get(key);
  if (!messages) {
    messages = loadMessages(key);
    conversations.set(key, messages);
  }
  return messages;
}

export const getServerMessages = () => EMPTY_MESSAGES;

export function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function setMessages(key: string, update: (current: LeoMessage[]) => LeoMessage[]) {
  const next = update(getMessages(key));
  conversations.set(key, next);
  if (!next.some((m) => m.status === "streaming")) saveMessages(key, next);
  for (const listener of listeners) listener();
}

export function updateMessage(key: string, id: string, update: (message: LeoMessage) => LeoMessage) {
  setMessages(key, (current) => current.map((m) => (m.id === id ? update(m) : m)));
}
