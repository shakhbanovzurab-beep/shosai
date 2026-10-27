import { describe, expect, it } from "vitest";

import { operatorImageUrl } from "./artifacts";

describe("the operator's pictures", () => {
  it("are read from the admin's route by their id", () => {
    expect(operatorImageUrl("01a17c52-47bc-7317-bdd4-55c14fa63171")).toBe(
      "/v1/admin/agent/images/01a17c52-47bc-7317-bdd4-55c14fa63171",
    );
    expect(operatorImageUrl("a/b?c")).toBe("/v1/admin/agent/images/a%2Fb%3Fc");
  });
});
