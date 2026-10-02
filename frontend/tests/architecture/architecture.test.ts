// @vitest-environment node
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { checkArchitecture } from "./checkArchitecture";
import { readProjectSources } from "./readSources";

const FRONTEND_ROOT = fileURLToPath(new URL("../..", import.meta.url));

describe("архитектура фронтенда", () => {
  const sources = readProjectSources(FRONTEND_ROOT);

  it("читает дерево исходников целиком", () => {
    // Пустой обход прошёл бы проверку ниже без единой строки кода.
    expect(sources.map((source) => source.path)).toContain("src/entrypoints/main.tsx");
  });

  it("не нарушает ни одного правила", () => {
    expect(checkArchitecture(sources)).toEqual([]);
  });
});
