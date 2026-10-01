// Веб-сокеты состояния. Сервера нет: подставной сокет Playwright отвечает
// странице сам. По умолчанию он молчит, как сервер без событий; состояние может
// задать кадры, которые уходят сразу после подключения (голосовой режим Leo,
// напоминание в /v1/ws/user), и кадры в ответ на первое сообщение страницы.

import type { BrowserContext } from "@playwright/test";

import type { JsonValue } from "../fixtures/format.ts";
import type { SocketScript } from "../states/types.ts";

const encode = (frame: JsonValue): string => (typeof frame === "string" ? frame : JSON.stringify(frame));

export async function routeSockets(context: BrowserContext, scripts: readonly SocketScript[]): Promise<void> {
  await context.routeWebSocket(/\/v1\/ws\//, (socket) => {
    const path = new URL(socket.url()).pathname;
    const script = scripts.find((candidate) => candidate.path === path);
    if (script === undefined) return;
    let answered = false;
    socket.onMessage(() => {
      if (answered) return;
      answered = true;
      for (const frame of script.afterClient ?? []) socket.send(encode(frame));
    });
    for (const frame of script.frames) socket.send(encode(frame));
  });
}

/** id пользователя из сохранённой сессии фикстуры (wh-auth) или null у гостя. */
export function storedUserId(storage: Readonly<Record<string, string>>): string | null {
  const raw = storage["wh-auth"];
  if (raw === undefined) return null;
  const parsed = JSON.parse(raw) as { state?: { user?: { id?: unknown } } };
  const id = parsed.state?.user?.id;
  return typeof id === "string" ? id : null;
}
