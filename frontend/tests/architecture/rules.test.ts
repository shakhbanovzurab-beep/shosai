// @vitest-environment node
import { describe, expect, it } from "vitest";

import { ALLOWED_TREE } from "./allowedTree";
import { BOUNDARY_FIXTURES } from "./boundaryFixtures";
import { checkArchitecture } from "./checkArchitecture";
import { CODE_FIXTURES } from "./codeFixtures";
import { toSources } from "./fixtureTree";
import type { RuleId } from "./violations";

const FIXTURES = [...BOUNDARY_FIXTURES, ...CODE_FIXTURES];
const ALL_RULES: readonly RuleId[] = [
  "layers",
  "slice-contracts",
  "shell-knows-no-slice",
  "pure-model",
  "ui-without-http",
  "no-raw-http",
  "query-keys-in-keys-modules",
  "lazy-in-manifests",
  "no-barrels",
  "no-cycles",
];

describe("правила архитектуры на фикстурах", () => {
  it.each(FIXTURES)("$rule: $name", ({ rule, tree }) => {
    const fired = new Set(checkArchitecture(toSources(tree)).map((violation) => violation.rule));
    expect(fired).toEqual(new Set([rule]));
  });

  it("у каждого правила есть фикстура", () => {
    expect(new Set(FIXTURES.map((fixture) => fixture.rule))).toEqual(new Set(ALL_RULES));
  });

  it("законные связи не нарушают ни одного правила", () => {
    expect(checkArchitecture(toSources(ALLOWED_TREE))).toEqual([]);
  });

  it("нарушение указывает модуль и строку", () => {
    const text = "// Первая строка по-русски\n\n\nexport const load = () => fetch('/v1/a');\n";
    const violations = checkArchitecture([{ path: "src/features/a/api/load.ts", text }]);
    expect(violations).toEqual([
      expect.objectContaining({ rule: "no-raw-http", path: "src/features/a/api/load.ts", line: 4 }),
    ]);
  });

  it("модуль, который не разбирается, роняет проверку", () => {
    expect(() => checkArchitecture([{ path: "src/core/lib/x.ts", text: "export const = ;" }])).toThrow(
      /src\/core\/lib\/x\.ts/,
    );
  });
});
