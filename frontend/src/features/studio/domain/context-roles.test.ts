import { describe, expect, it } from "vitest";

import { isSwitchedOn, switched } from "./context-roles";

describe("куда подмешивать контекст", () => {
  it("при «Все» отдельные роли выключены", () => {
    expect(isSwitchedOn("all", "all")).toBe(true);
    expect(isSwitchedOn("all", "code")).toBe(false);
    expect(isSwitchedOn(["code"], "code")).toBe(true);
  });

  it("включённая роль выключает «Все», а «Все» выключает отдельные роли", () => {
    expect(switched("all", "notes", true)).toEqual(["notes"]);
    expect(switched(["notes", "code"], "all", true)).toBe("all");
    expect(switched("all", "all", false)).toEqual([]);
  });

  it("роли идут в порядке Studio, без повторов", () => {
    expect(switched(["notes"], "live_answers", true)).toEqual(["live_answers", "notes"]);
    expect(switched(["code", "notes"], "code", true)).toEqual(["code", "notes"]);
    expect(switched(["code", "notes"], "code", false)).toEqual(["notes"]);
  });
});
