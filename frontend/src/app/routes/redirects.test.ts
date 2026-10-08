import { describe, expect, it } from "vitest";

import { redirectTarget } from "./redirects";

describe("redirectTarget", () => {
  it("keeps the source's query parameters", () => {
    expect(redirectTarget("https://x.test/app/team?from=mail", "/app/w")).toBe("/app/w?from=mail");
  });

  it("adds them to the target's own without overriding it", () => {
    expect(redirectTarget("https://x.test/admin/crm?tab=x&a=1", "/admin/dashboard?tab=crm")).toBe(
      "/admin/dashboard?tab=crm&a=1",
    );
  });
});
