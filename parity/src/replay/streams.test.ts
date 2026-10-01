// Потоки и сокеты состояния: кадры SSE, открытые потоки, id пользователя для
// ключей localStorage.

import { expect, test } from "@playwright/test";

import { openStreamsOf } from "../determinism/open-streams.ts";
import { hold, openStream, reply, stream, streamBody } from "../states/overrides.ts";
import { storedUserId } from "./sockets.ts";

test("именованное событие — строки event и data, данные в JSON", () => {
  expect(streamBody([{ event: "token", data: { text: "Привет" } }])).toBe('event: token\ndata: {"text":"Привет"}\n\n');
});

test("событие без имени — голый кадр data; строка уходит как есть", () => {
  expect(streamBody([{ event: "", data: { choices: [] } }, { event: "", data: "[DONE]" }]))
    .toBe('data: {"choices":[]}\n\ndata: [DONE]\n\n');
});

test("законченный поток — ответ 200 с телом SSE", () => {
  const override = stream("POST", "/v1/ai/agent/chat", [{ event: "done", data: {} }], "модели нет");
  expect(override.respond).toEqual({ status: 200, body: "event: done\ndata: {}\n\n", contentType: "text/event-stream" });
});

test("открытые потоки состояния — только ответы `open`, с типом по умолчанию", () => {
  const streams = openStreamsOf([
    openStream("POST", "/v1/ai/agent/chat", [{ event: "token", data: { text: "а" } }], "модели нет"),
    hold("GET", "/v1/me"),
    reply("GET", "/v1/hubs", 200, { items: [] }, "пусто"),
  ]);
  expect(streams).toEqual([
    { method: "POST", path: "/v1/ai/agent/chat", body: 'event: token\ndata: {"text":"а"}\n\n', contentType: "text/event-stream" },
  ]);
});

test("id пользователя берётся из сохранённой сессии, у гостя его нет", () => {
  const session = JSON.stringify({ state: { csrfToken: "x", user: { id: "00000000-0000-4000-8000-000000000001" } }, version: 0 });
  expect(storedUserId({ "wh-auth": session })).toBe("00000000-0000-4000-8000-000000000001");
  expect(storedUserId({})).toBeNull();
  expect(storedUserId({ "wh-auth": JSON.stringify({ state: { user: null }, version: 0 }) })).toBeNull();
});
