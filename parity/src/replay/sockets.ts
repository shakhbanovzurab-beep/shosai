// Веб-сокеты состояния. Сервера нет: перехватывается каждый сокет страницы, и
// подставной сокет Playwright отвечает ей сам. Сокет своего API (/v1/…) по
// умолчанию молчит, как сервер без событий; состояние может задать кадры сразу
// после подключения (голосовой режим Leo, напоминание в /v1/ws/user) и кадры в
// ответ на первое сообщение страницы. Сокет на чужой хост (медиасервер LiveKit
// из ответа на вход в комнату) закрывается сразу: в сеть стенд не ходит.

import type { BrowserContext } from "@playwright/test";

import type { JsonValue } from "../fixtures/format.ts";
import type { SocketScript } from "../states/types.ts";

/** Сокеты своего API: без сценария молчат, остальные закрываются. */
const API_PREFIX = "/v1/";

const encode = (frame: JsonValue): string => (typeof frame === "string" ? frame : JSON.stringify(frame));

export async function routeSockets(context: BrowserContext, scripts: readonly SocketScript[]): Promise<void> {
  await context.routeWebSocket(/.*/, (socket) => {
    const path = new URL(socket.url()).pathname;
    const script = scripts.find((candidate) => candidate.path === path);
    if (script === undefined) {
      if (!path.startsWith(API_PREFIX)) void socket.close();
      return;
    }
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
