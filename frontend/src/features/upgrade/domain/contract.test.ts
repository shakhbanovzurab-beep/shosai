import { describe, expectTypeOf, it } from "vitest";

import type { components } from "@/lib/api/generated/schema";

import type { PlansResponse } from "./contract";

type Schemas = components["schemas"];

// Планы кабинета и ответ бэкенда (billing, шаг 6) совпадают поле в поле: расхождение ломает typecheck.
describe("upgrade contract", () => {
  it("matches the backend's plans", () => {
    expectTypeOf<
      Schemas["shosai__features__billing__channels__http__plans__PlansView"]
    >().toEqualTypeOf<PlansResponse>();
  });
});
