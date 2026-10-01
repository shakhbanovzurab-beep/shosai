// Нормализация фикстуры: токены, UUID, «сейчас» и случайные поля ответов.

import { expect, test } from "@playwright/test";

import type { Exchange, Fixture } from "../fixtures/format.ts";
import { normalizeFixture } from "./normalize.ts";

const CLOCK = new Date("2026-07-17T12:00:00Z");

function fixtureWith(exchanges: Exchange[], storage: Record<string, string> = {}): Fixture {
  return {
    visit: "unit/test",
    language: "ru",
    persona: "free",
    url: "/app/",
    draftCommit: "0",
    clock: CLOCK.toISOString(),
    storage,
    exchanges,
  };
}

function get(path: string, body: Exchange["body"], method = "GET"): Exchange {
  return { method, path, query: "", status: 200, contentType: "application/json", body, origin: "recorded" };
}

test("UUID заменяются заглушками одинаково в хранилище, путях и телах", () => {
  const id = "3f2b8c1e-9a4d-4e2b-8c1a-0123456789ab";
  const result = normalizeFixture(
    fixtureWith([get(`/v1/items/${id}`, { id, owner: { id } })], { "wh-auth": JSON.stringify({ user: { id } }) }),
    CLOCK,
  );
  const placeholder = "00000000-0000-4000-8000-000000000001";
  expect(result.storage["wh-auth"]).toBe(JSON.stringify({ user: { id: placeholder } }));
  expect(result.exchanges[0]?.path).toBe(`/v1/items/${placeholder}`);
  expect(result.exchanges[0]?.body).toEqual({ id: placeholder, owner: { id: placeholder } });
});

test("«сейчас» в пределах суток после момента — сам момент в том же формате; прочее не трогается", () => {
  const result = normalizeFixture(
    fixtureWith([
      get("/v1/me", {
        seen: "2026-07-17T12:03:41.123456+00:00",
        logged: "2026-07-17T12:00:09Z",
        paid: "2026-07-07T12:00:00+00:00",
        expires: "2026-08-07T12:00:00+00:00",
      }),
    ]),
    CLOCK,
  );
  expect(result.exchanges[0]?.body).toEqual({
    seen: "2026-07-17T12:00:00.000000+00:00",
    logged: "2026-07-17T12:00:00Z",
    paid: "2026-07-07T12:00:00+00:00",
    expires: "2026-08-07T12:00:00+00:00",
  });
});

test("токены и JWT заменяются, код тарифа — нет", () => {
  // Токен собирается здесь же из JSON: в исходниках не должно быть ничего,
  // похожего на настоящий JWT.
  const part = (value: object): string => Buffer.from(JSON.stringify(value)).toString("base64url");
  const jwt = [part({ alg: "HS256" }), part({ sub: "parity" }), "c2lnbmF0dXJl"].join(".");
  const result = normalizeFixture(
    fixtureWith([get("/v1/auth/refresh", { access_token: "abc", csrf_token: "def", note: `Bearer ${jwt}`, code: "free" }, "POST")]),
    CLOCK,
  );
  expect(result.exchanges[0]?.body).toEqual({
    access_token: "parity-access_token",
    csrf_token: "parity-csrf_token",
    note: "Bearer parity.jwt.token",
    code: "free",
  });
});

test("случайные поля конкретных ответов заменяются только в них", () => {
  const result = normalizeFixture(
    fixtureWith([
      get("/v1/auth/desktop/code", { code: "123456", expires_in: 120 }, "POST"),
      get("/v1/auth/social/vk/prepare", { state: "s", code_verifier: "v", app_id: "51000000" }),
    ]),
    CLOCK,
  );
  expect(result.exchanges[0]?.body).toEqual({ code: "parity-code", expires_in: 120 });
  expect(result.exchanges[1]?.body).toEqual({ state: "parity-state", code_verifier: "parity-code_verifier", app_id: "51000000" });
});

test("адрес визита получает те же заглушки, что пути запросов", () => {
  const id = "5eed0001-0000-4000-8000-0000000000a1";
  const segment = "5eed0002-0000-4000-8000-0000000000b5";
  const result = normalizeFixture(
    { ...fixtureWith([get(`/v1/me/sessions/${id}/full`, { segments: [{ id: segment }] })]), url: `/app/meetings/${id}#seg-${segment}` },
    CLOCK,
  );
  expect(result.exchanges[0]?.path).toBe("/v1/me/sessions/00000000-0000-4000-8000-000000000001/full");
  expect(result.url).toBe("/app/meetings/00000000-0000-4000-8000-000000000001#seg-00000000-0000-4000-8000-000000000002");
});

test("случайные идентификаторы участников заменяются заглушками по порядку появления", () => {
  const user = "5eed0000-0000-4000-8000-0000000000aa";
  const normalized = normalizeFixture(
    fixtureWith([
      get("/v1/streams/live/state", { me: `${user}__1a2b3c4d`, guests: ["guest-0123456789ab", "guest-ba9876543210"] }),
      get("/v1/streams/live/chat", [{ principal: "guest-0123456789ab" }, { identity: `${user}__1a2b3c4d` }]),
    ]),
    CLOCK,
  );
  const placeholder = "00000000-0000-4000-8000-000000000001";
  expect(normalized.exchanges[0]?.body).toEqual({
    me: `${placeholder}__00000001`,
    guests: ["guest-000000000001", "guest-000000000002"],
  });
  expect(normalized.exchanges[1]?.body).toEqual([{ principal: "guest-000000000001" }, { identity: `${placeholder}__00000001` }]);
});

test("группы без порядка у черновика — по убыванию числа, затем по ключу, только в объявленных ответах", () => {
  const result = normalizeFixture(fixtureWith([
    get("/v1/admin/dashboard", { users_by_tariff: { start: 1, free: 13, pro_1m: 6, max_1m: 2 }, other: { b: 1, a: 2 } }),
    get("/v1/admin/analytics/onboarding", { steps: [{ key: "hub", count: 1 }, { key: "map", count: 5 }, { key: "audio", count: 1 }] }),
  ]), CLOCK);
  const [dashboard, onboarding] = result.exchanges.map((exchange) => JSON.stringify(exchange.body));
  expect(dashboard).toBe('{"users_by_tariff":{"free":13,"pro_1m":6,"max_1m":2,"start":1},"other":{"b":1,"a":2}}');
  expect(onboarding).toBe('{"steps":[{"key":"map","count":5},{"key":"audio","count":1},{"key":"hub","count":1}]}');
});
