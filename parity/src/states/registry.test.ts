// Целостность реестра состояний и соответствие синтетических ответов контракту
// черновика (D1).

import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

import { expect, test } from "@playwright/test";

import { FIXTURES_DIR } from "../config.ts";
import { DraftContract } from "../contracts/draft-openapi.ts";
import type { Fixture } from "../fixtures/format.ts";
import { ALL_STATES, registryProblems } from "./registry.ts";

test("реестр состояний целостен: id уникальны, фикстуры есть, у синтетики есть причина", () => {
  expect(registryProblems(ALL_STATES, FIXTURES_DIR)).toEqual([]);
});

test("синтетические ответы существуют в контракте черновика и подходят под его схемы", () => {
  const contract = new DraftContract();
  const problems: string[] = [];
  for (const state of ALL_STATES) {
    for (const override of state.overrides ?? []) {
      const operation = contract.operation(override.method, override.path);
      if (operation === null) {
        problems.push(`${state.id}: ${override.method} ${override.path} нет в OpenAPI черновика`);
        continue;
      }
      const replies = Array.isArray(override.respond) ? override.respond : [override.respond];
      for (const reply of replies) {
        // Записанный ответ и его правка — данные черновика, их проверяет запись.
        if (typeof reply === "string" || "merge" in reply || "open" in reply) continue;
        // Поток событий (SSE) — не JSON: его схему OpenAPI не описывает.
        if (reply.contentType !== undefined && !reply.contentType.includes("json")) continue;
        for (const problem of contract.bodyProblems(operation, reply.status, reply.body)) {
          problems.push(`${state.id}: ${override.method} ${override.path} ${reply.status}: ${problem}`);
        }
      }
    }
  }
  expect(problems).toEqual([]);
});

test("проверка контракта замечает выдуманный путь и тело не по схеме", () => {
  const contract = new DraftContract();
  expect(contract.operation("GET", "/v1/no/such/route")).toBeNull();
  const onboarding = contract.operation("GET", "/v1/me/onboarding");
  expect(onboarding).not.toBeNull();
  if (onboarding !== null) expect(contract.bodyProblems(onboarding, 200, { status: 1 }).length).toBeGreaterThan(0);
});

test("синтетические обмены в фикстурах — с причиной, в контракте черновика и по его схемам", () => {
  const contract = new DraftContract();
  const problems: string[] = [];
  const files = readdirSync(FIXTURES_DIR, { recursive: true, encoding: "utf8" }).filter((file) => file.endsWith(".json"));
  for (const file of files) {
    const fixture = JSON.parse(readFileSync(path.join(FIXTURES_DIR, file), "utf8")) as Fixture;
    for (const exchange of fixture.exchanges.filter((candidate) => candidate.origin === "synthetic")) {
      const where = `${file}: ${exchange.method} ${exchange.path}`;
      if ((exchange.reason ?? "").trim() === "") problems.push(`${where}: без причины`);
      const operation = contract.operation(exchange.method, exchange.path);
      if (operation === null) {
        problems.push(`${where}: нет в OpenAPI черновика`);
        continue;
      }
      for (const problem of contract.bodyProblems(operation, exchange.status, exchange.body)) problems.push(`${where}: ${problem}`);
    }
  }
  expect(problems).toEqual([]);
});
