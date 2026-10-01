// Строгое воспроизведение: сопоставление по ключу, очередь повторов,
// переопределения состояния, фоновые запросы и учёт запросов без ответа.

import { expect, test } from "@playwright/test";
import type { Route } from "@playwright/test";

import { ORIGIN } from "../config.ts";
import type { Exchange, Fixture } from "../fixtures/format.ts";
import { openStream, stream } from "../states/overrides.ts";
import { FixtureReplay } from "./replay.ts";

interface Outcome {
  fulfilled?: { status: number; body: string };
  aborted?: string;
}

/** Маршрут-заглушка: запоминает, чем на него ответили. */
function fakeRoute(method: string, outcome: Outcome): Route {
  return {
    request: () => ({ method: () => method }),
    fulfill: async (reply: { status: number; body: Buffer }) => {
      outcome.fulfilled = { status: reply.status, body: reply.body.toString("utf8") };
    },
    abort: async (code: string) => {
      outcome.aborted = code;
    },
  } as unknown as Route;
}

function exchange(path: string, body: Exchange["body"], query = ""): Exchange {
  return { method: "GET", path, query, status: 200, contentType: "application/json", body, origin: "recorded" };
}

function fixture(exchanges: Exchange[]): Fixture {
  return {
    visit: "unit/test",
    language: "ru",
    persona: null,
    url: "/app/",
    draftCommit: "0",
    clock: "2026-07-17T12:00:00.000Z",
    storage: {},
    exchanges,
  };
}

async function call(replay: FixtureReplay, method: string, url: string): Promise<Outcome> {
  const outcome: Outcome = {};
  await replay.handle(fakeRoute(method, outcome), new URL(`${ORIGIN}${url}`));
  return outcome;
}

test("повторы одного ключа получают записанные ответы по очереди, последний повторяется", async () => {
  const replay = new FixtureReplay(fixture([exchange("/v1/me", { n: 1 }), exchange("/v1/me", { n: 2 })]), []);
  expect((await call(replay, "GET", "/v1/me")).fulfilled?.body).toBe('{"n":1}');
  expect((await call(replay, "GET", "/v1/me")).fulfilled?.body).toBe('{"n":2}');
  expect((await call(replay, "GET", "/v1/me")).fulfilled?.body).toBe('{"n":2}');
  expect(replay.unmatched).toEqual([]);
});

test("строка запроса сравнивается в каноническом порядке параметров", async () => {
  const replay = new FixtureReplay(fixture([exchange("/v1/search", [], "a=1&b=2")]), []);
  expect((await call(replay, "GET", "/v1/search?b=2&a=1")).fulfilled?.status).toBe(200);
  expect(replay.unmatched).toEqual([]);
});

test("запрос без записи отвечается 404 и попадает в список несопоставленных", async () => {
  const replay = new FixtureReplay(fixture([]), []);
  expect((await call(replay, "GET", "/v1/unknown?x=1")).fulfilled?.status).toBe(404);
  expect(replay.unmatched).toEqual(["GET /v1/unknown?x=1"]);
});

test("фоновый запрос без записи получает заданный ответ и ошибкой не считается", async () => {
  const replay = new FixtureReplay(fixture([]), []);
  expect((await call(replay, "POST", "/v1/satisfaction/prompt")).fulfilled?.body).toContain('"due":false');
  expect(replay.unmatched).toEqual([]);
});

test("последовательность ответов переопределения: по порядку, последний повторяется", async () => {
  const replay = new FixtureReplay(fixture([]), [
    { method: "GET", path: "/v1/health", respond: [{ status: 503, body: null }, "hold"], reason: "тест" },
  ]);
  expect((await call(replay, "GET", "/v1/health")).fulfilled?.status).toBe(503);
  expect(await call(replay, "GET", "/v1/health")).toEqual({});
  expect(await call(replay, "GET", "/v1/health")).toEqual({});
});

test("переопределение заменяет записанный ответ, hold не отвечает, fail обрывает", async () => {
  const replay = new FixtureReplay(fixture([exchange("/v1/me", { n: 1 })]), [
    { method: "GET", path: "/v1/me", respond: { status: 500, body: { detail: "x" } }, reason: "тест" },
    { method: "GET", path: "/v1/slow", respond: "hold", reason: "тест" },
    { method: "GET", path: "/v1/down", respond: "fail", reason: "тест" },
  ]);
  expect((await call(replay, "GET", "/v1/me")).fulfilled).toEqual({ status: 500, body: '{"detail":"x"}' });
  expect(await call(replay, "GET", "/v1/slow")).toEqual({});
  expect((await call(replay, "GET", "/v1/down")).aborted).toBe("failed");
  expect(replay.unmatched).toEqual([]);
});

test("поток событий отдаётся как есть, строка JSON — сериализованной", async () => {
  const replay = new FixtureReplay(fixture([]), [
    stream("POST", "/v1/stream", [{ event: "delta", data: { text: "a" } }, { event: "done", data: {} }], "тест"),
    { method: "GET", path: "/v1/text", respond: { status: 200, body: "ok" }, reason: "тест" },
  ]);
  expect((await call(replay, "POST", "/v1/stream")).fulfilled?.body).toBe('event: delta\ndata: {"text":"a"}\n\nevent: done\ndata: {}\n\n');
  expect((await call(replay, "GET", "/v1/text")).fulfilled?.body).toBe('"ok"');
});

test("ответ recorded в последовательности отдаёт записанное", async () => {
  const replay = new FixtureReplay(fixture([exchange("/v1/full", { n: 1 })]), [
    { method: "GET", path: "/v1/full", respond: ["recorded", "recorded", "hold"], reason: "тест" },
  ]);
  expect((await call(replay, "GET", "/v1/full")).fulfilled?.body).toBe('{"n":1}');
  expect((await call(replay, "GET", "/v1/full")).fulfilled?.body).toBe('{"n":1}');
  expect(await call(replay, "GET", "/v1/full")).toEqual({});
});

test("подмена по шаблону пути отвечает на любой id, точный путь важнее шаблона", async () => {
  const replay = new FixtureReplay(fixture([]), [
    { method: "DELETE", path: "/v1/items/{id}", respond: { status: 500, body: null }, reason: "тест" },
    { method: "DELETE", path: "/v1/items/kept", respond: { status: 204, body: null }, reason: "тест" },
  ]);
  expect((await call(replay, "DELETE", "/v1/items/abc")).fulfilled?.status).toBe(500);
  expect((await call(replay, "DELETE", "/v1/items/kept")).fulfilled?.status).toBe(204);
  expect((await call(replay, "DELETE", "/v1/items/abc/extra")).fulfilled?.status).toBe(404);
});

test("правка записанного ответа вливает поля глубоко, массивы заменяет", async () => {
  const replay = new FixtureReplay(fixture([exchange("/v1/space", { used: 1, quota: { limit: 10, ratio: 0.1 }, tags: ["a"] })]), [
    { method: "GET", path: "/v1/space", respond: { merge: { quota: { ratio: 0.9 }, tags: ["b"] } }, reason: "тест" },
  ]);
  expect(JSON.parse((await call(replay, "GET", "/v1/space")).fulfilled?.body ?? "")).toEqual({
    used: 1,
    quota: { limit: 10, ratio: 0.9 },
    tags: ["b"],
  });
});

test("открытый поток, дошедший до сети, — сбой стенда: запрос попадает в несопоставленные", async () => {
  const replay = new FixtureReplay(fixture([]), [openStream("POST", "/v1/ai/agent/chat", [], "модели нет")]);
  expect((await call(replay, "POST", "/v1/ai/agent/chat")).aborted).toBe("failed");
  expect(replay.unmatched).toEqual(["POST /v1/ai/agent/chat (открытый поток дошёл до сети)"]);
});
