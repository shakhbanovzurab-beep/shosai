import openapiTS, { astToString, COMMENT_HEADER } from "openapi-typescript";
import { describe, expect, it } from "vitest";

import { readFileSync } from "node:fs";

const DOCUMENT = new URL("../../backend/openapi.json", import.meta.url);
const TYPES = new URL("../src/lib/api/generated/schema.d.ts", import.meta.url);

// Типы клиента генерируются из контракта бэкенда; устаревшие типы — ошибка, а не тихое расхождение.
describe("API types", () => {
  it("are generated from backend/openapi.json (npm run api:types)", async () => {
    const generated = COMMENT_HEADER + astToString(await openapiTS(DOCUMENT));
    expect(readFileSync(TYPES, "utf8")).toBe(generated);
  });
});
