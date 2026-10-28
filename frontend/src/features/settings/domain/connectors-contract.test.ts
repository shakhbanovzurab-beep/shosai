import { describe, expect, it } from "vitest";

import { CONNECTOR_CATEGORIES, CONNECTOR_PROBLEMS, FLOW_ERRORS } from "./connectors-contract";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

/*
 * Кабинет называет словами каждый код, который присылает бэкенд коннекторов: проблему строки, ошибку потока OAuth и
 * категорию. Список кодов кабинета сверяется с перечислениями домена бэкенда, иначе новый код покажется без слов.
 */

const DOMAIN = "../../../../../backend/src/shosai/features/connectors/domain/";
const source = (file: string) => readFileSync(fileURLToPath(new URL(DOMAIN + file, import.meta.url)), "utf8");

// Значения StrEnum класса: строки вида `    NAME = "value"` до следующего класса.
function enumValues(file: string, name: string): string[] {
  const body =
    source(file)
      .split(`class ${name}(StrEnum):`)[1]
      ?.split(/^class /m)[0] ?? "";
  return [...body.matchAll(/^ {4}[A-Z_]+ = "([a-z_]+)"$/gm)].map((match) => match[1] ?? "");
}

// Установку в командный чат называют чаты (поток `flow=chats`), не Settings › Connectors.
const CHATS_ONLY = new Set(["installed_elsewhere"]);

describe("the connectors codes the cabinet words", () => {
  it("cover every problem of a connection", () => {
    expect([...CONNECTOR_PROBLEMS].sort()).toEqual(enumValues("states.py", "Problem").sort());
  });

  it("cover every error of a connect flow outside chats", () => {
    const flowErrors = enumValues("flows.py", "FlowError").filter((code) => !CHATS_ONLY.has(code));
    expect([...FLOW_ERRORS].sort()).toEqual(flowErrors.sort());
  });

  it("cover every category of the catalogue", () => {
    expect([...CONNECTOR_CATEGORIES].sort()).toEqual(enumValues("catalogue.py", "Category").sort());
  });
});
