import type { LeoMessage } from "../domain/types";

/* Примерные разговоры Leo — хаба и админки до их шагов — по контексту, вне React и только в памяти страницы. */

const EMPTY_MESSAGES: LeoMessage[] = [];
// Ключи, под которыми разговор раньше лежал в браузере: панель их стирает и больше ничего не пишет.
const OLD_STORAGE_PREFIX = "leo-chat";

let idCounter = 0;
export const createId = () => `${Date.now().toString(36)}-${(idCounter++).toString(36)}`;

/** Стереть разговоры, сохранённые в браузере прежней панелью: разговор теперь живёт только на сервере. */
export function forgetStoredConversations() {
  try {
    const stale = Object.keys(window.localStorage).filter((key) => key.startsWith(OLD_STORAGE_PREFIX));
    for (const key of stale) window.localStorage.removeItem(key);
  } catch {
    // Хранилище недоступно (приватный режим): стирать нечего.
  }
}

// File contents stay in memory for this page session only, keyed by message id, so "Regenerate"
// can send them again. After a reload only the attachment metadata remains.
export const attachmentFiles = new Map<string, File[]>();

const conversations = new Map<string, LeoMessage[]>();
const listeners = new Set<() => void>();

export const getMessages = (key: string): LeoMessage[] => conversations.get(key) ?? EMPTY_MESSAGES;

export const getServerMessages = () => EMPTY_MESSAGES;

export function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function setMessages(key: string, update: (current: LeoMessage[]) => LeoMessage[]) {
  conversations.set(key, update(getMessages(key)));
  for (const listener of listeners) listener();
}

export function updateMessage(key: string, id: string, update: (message: LeoMessage) => LeoMessage) {
  setMessages(key, (current) => current.map((m) => (m.id === id ? update(m) : m)));
}
