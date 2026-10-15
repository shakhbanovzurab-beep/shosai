import { describe, expect, it } from "vitest";

import { userSearchOf } from "./search";

describe("userSearchOf", () => {
  it("reads an address as an email search and anything else as a name", () => {
    expect(userSearchOf(" Ivan@Example.com ")).toEqual({ email: "Ivan@Example.com" });
    expect(userSearchOf("иван")).toEqual({ name: "иван" });
  });

  it("waits for at least two letters of a name", () => {
    expect(userSearchOf("")).toBeNull();
    expect(userSearchOf(" и ")).toBeNull();
    expect(userSearchOf("x".repeat(81))).toBeNull();
  });
});
