import { describe, expectTypeOf, it } from "vitest";

import type { components } from "@/lib/api/generated/schema";

import type { Usage } from "./billing-contract";

type Schemas = components["schemas"];

// Использование кабинета и ответ бэкенда (billing, шаг 6) совпадают поле в поле: расхождение ломает typecheck.
describe("usage contract", () => {
  it("matches the backend's week of tokens", () => {
    expectTypeOf<Schemas["UsageView"]>().toEqualTypeOf<Usage>();
  });
});
