import { describe, expect, it } from "vitest";

import { sha256, toHex } from "./sha256";
import { createHash } from "node:crypto";

describe("sha256", () => {
  it("matches Node's SHA-256 for short, block-sized and long texts", () => {
    for (const text of ["", "abc", "a".repeat(55), "a".repeat(64), "Привет, 世界".repeat(40)])
      expect(toHex(sha256(text))).toBe(createHash("sha256").update(text).digest("hex"));
  });
});
