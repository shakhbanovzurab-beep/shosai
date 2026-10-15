import { describe, expect, it } from "vitest";

import { HOME_PATH, loginPathFor, safeNext } from "./next-path";

describe("safeNext", () => {
  it("keeps a page of either panel", () => {
    expect(safeNext("/app/notes/42?tab=tasks")).toBe("/app/notes/42?tab=tasks");
    expect(safeNext("/admin/users")).toBe("/admin/users");
  });

  it("turns anything else into home", () => {
    for (const raw of [
      null,
      "",
      "https://evil.example",
      "//evil.example/app",
      "/\\evil",
      "/apple",
      "/app/login",
      "/app/register?x=1",
      "/app/forgot",
      "/app/reset?token=t",
    ]) {
      expect(safeNext(raw)).toBe(HOME_PATH);
    }
  });
});

describe("loginPathFor", () => {
  it("carries the page to return to", () => {
    expect(loginPathFor("/app/kanban")).toBe("/app/login?next=%2Fapp%2Fkanban");
    expect(loginPathFor("/app")).toBe("/app/login");
  });
});
