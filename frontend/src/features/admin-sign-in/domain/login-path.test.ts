import { describe, expect, it } from "vitest";

import { adminLoginPathOf } from "./login-path";

const SCREENS = ["dashboard", "users", "workspaces"];

describe("adminLoginPathOf", () => {
  it("takes one long lowercase segment under /admin", () => {
    expect(adminLoginPathOf(" /admin/staff-k3q9x2m ", SCREENS)).toBe("/admin/staff-k3q9x2m");
  });

  it("refuses short, nested, uppercase, outside and missing paths", () => {
    for (const value of [undefined, "", "/admin", "/admin/staff", "/staff-k3q9x2m", "/admin/Staff-k3q9x2m"]) {
      expect(adminLoginPathOf(value, SCREENS)).toBeNull();
    }
    expect(adminLoginPathOf("/admin/staff/k3q9x2m", SCREENS)).toBeNull();
  });

  it("refuses the address of an admin screen", () => {
    expect(adminLoginPathOf("/admin/dashboard", SCREENS)).toBeNull();
  });
});
