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
