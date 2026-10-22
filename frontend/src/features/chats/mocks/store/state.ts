import { seedConnections } from "../seed/connections";
import { seedDigests } from "../seed/digests";
import { seedSlack } from "../seed/slack";
import type { ChatsDemo } from "./types";

/*
 * Хранилище моков командных чатов в памяти вкладки; сбрасывается перезагрузкой. Одно на страницу, поэтому
 * живёт на globalThis, как хранилища других слайсов.
 */

function seeded(): ChatsDemo {
  const demo: ChatsDemo = {
    settings: new Map(),
    connections: new Map(),
    codes: new Map(),
    installations: new Map(),
    channels: new Map(),
    consents: new Map(),
    digests: new Map(),
    joined: 0,
  };
  seedConnections(demo);
  seedSlack(demo);
  seedDigests(demo);
  return demo;
}

const shared = globalThis as typeof globalThis & { chatsDemo?: ChatsDemo };

export function demo(): ChatsDemo {
  shared.chatsDemo ??= seeded();
  return shared.chatsDemo;
}

/** Начать с чистых демо-данных — для тестов. */
export function resetDemo() {
  shared.chatsDemo = seeded();
  return shared.chatsDemo;
}

export const now = () => new Date().toISOString();

/**
 * Переключатель демо в sessionStorage: чем кончаются новые коды Telegram и запросы привязки — `expire`,
 * `refuse` (группа уже подключена к другому пространству) или `member` (бот вошёл без прав администратора).
 * Без него код подключается, как обычно.
 */
export const CHATS_DEMO_SWITCH = "chats-demo";

export function demoOutcome(): "expire" | "refuse" | "member" | null {
  try {
    const value = globalThis.sessionStorage?.getItem(CHATS_DEMO_SWITCH);
    return value === "expire" || value === "refuse" || value === "member" ? value : null;
  } catch {
    return null;
  }
}
