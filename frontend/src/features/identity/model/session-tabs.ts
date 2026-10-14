/**
 * Вкладки одного браузера делят refresh-cookie, поэтому обновляют её по очереди: Web Lock держит одно
 * обновление на весь браузер, а канал сообщает остальным вкладкам новый токен или выход. Где этих API нет,
 * вкладка работает одна — сервер всё равно прощает повтор старого refresh в течение 10 секунд.
 */

const CHANNEL = "shosai-session";
const LOCK = "shosai-session-refresh";

export type TabMessage = { kind: "token"; token: string } | { kind: "signed-out" };

let channel: BroadcastChannel | null = null;

function isTabMessage(value: unknown): value is TabMessage {
  if (typeof value !== "object" || value === null) return false;
  const message = value as { kind?: unknown; token?: unknown };
  return message.kind === "signed-out" || (message.kind === "token" && typeof message.token === "string");
}

/** Слушать другие вкладки; повторный вызов не открывает второй канал. */
export function listenToTabs(onMessage: (message: TabMessage) => void): void {
  if (channel !== null || typeof BroadcastChannel === "undefined") return;
  channel = new BroadcastChannel(CHANNEL);
  channel.addEventListener("message", (event: MessageEvent<unknown>) => {
    if (isTabMessage(event.data)) onMessage(event.data);
  });
}

export function tellTabs(message: TabMessage): void {
  channel?.postMessage(message);
}

/** Выполнить работу, пока ни одна другая вкладка не обновляет сессию. */
export async function exclusively<T>(work: () => Promise<T>): Promise<T> {
  const locks = typeof navigator === "undefined" ? undefined : navigator.locks;
  return locks ? await locks.request(LOCK, work) : await work();
}
