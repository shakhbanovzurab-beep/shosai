import { describe, expect, it } from "vitest";

import { acceptablePassword, checkPassword } from "./password-rules";

describe("checkPassword", () => {
  it("names what a short lowercase password still lacks", () => {
    expect(checkPassword("abc")).toEqual({ strength: "weak", score: 0, unmet: ["length", "case", "number", "symbol"] });
  });

  it("counts letters, digits and symbols of any script", () => {
    expect(checkPassword("Пароль§١٢٣ß").unmet).toEqual([]);
    expect(checkPassword("Пароль§١٢٣ß").strength).toBe("strong");
  });

  it("grades by the number of rules met", () => {
    expect(checkPassword("quietroom").strength).toBe("weak");
    expect(checkPassword("Quietroom").strength).toBe("fair");
    expect(checkPassword("Quietroom4").strength).toBe("good");
  });
});

describe("acceptablePassword", () => {
  it("follows the server's length rule only", () => {
    expect(acceptablePassword("1234567")).toBe(false);
    expect(acceptablePassword("12345678")).toBe(true);
    expect(acceptablePassword("x".repeat(257))).toBe(false);
  });
});
