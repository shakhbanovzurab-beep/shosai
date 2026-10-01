// Потоки, которые не заканчиваются: экран «ответ ещё печатается».
//
// Ответ Playwright (route.fulfill) отдаёт тело целиком и закрывает его, а
// фронтенд по закрытию потока снимает ожидание. Поэтому открытый поток отдаёт
// сама страница: скрипт до загрузки приложения подменяет fetch для заданных
// метода и пути и возвращает ответ, у которого тело — поток событий без конца.
// Так фронтенд читает SSE на POST (fetch-event-source); запрос до сети не доходит.

import type { BrowserContext } from "@playwright/test";

import type { Override } from "../states/types.ts";

interface OpenStream {
  readonly method: string;
  readonly path: string;
  readonly body: string;
  readonly contentType: string;
}

/** Открытые потоки состояния: подмены, ответ которых — `{ open }`. */
export function openStreamsOf(overrides: readonly Override[]): OpenStream[] {
  return overrides.flatMap((override) => {
    const replies = Array.isArray(override.respond) ? override.respond : [override.respond];
    const open = replies.find((reply) => typeof reply === "object" && "open" in reply);
    if (open === undefined || typeof open !== "object" || !("open" in open)) return [];
    return [{ method: override.method, path: override.path, body: open.open, contentType: open.contentType ?? "text/event-stream" }];
  });
}

export async function installOpenStreams(context: BrowserContext, streams: readonly OpenStream[]): Promise<void> {
  if (streams.length === 0) return;
  await context.addInitScript((list: readonly OpenStream[]) => {
    const original = window.fetch.bind(window);
    const matches = (template: string, path: string): boolean => {
      const expected = template.split("/");
      const actual = path.split("/");
      return expected.length === actual.length &&
        expected.every((segment, index) => (segment.startsWith("{") ? (actual[index] ?? "") !== "" : segment === actual[index]));
    };
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
      const href = input instanceof Request ? input.url : String(input);
      const path = new URL(href, window.location.href).pathname;
      const stream = list.find((candidate) => candidate.method === method && matches(candidate.path, path));
      if (stream === undefined) return original(input, init);
      const bytes = new TextEncoder().encode(stream.body);
      const body = new ReadableStream<Uint8Array>({ start: (controller) => controller.enqueue(bytes) });
      return new Response(body, { status: 200, headers: { "content-type": stream.contentType } });
    };
  }, streams);
}
