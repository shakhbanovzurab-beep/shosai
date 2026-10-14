import { describe, expect, it } from "vitest";

import { COUNTRY_CODES, countryFromLanguages, needsCrossBorderConsent } from "./countries";

describe("countryFromLanguages", () => {
  it("takes the first browser language that names a region", () => {
    expect(countryFromLanguages(["ru-RU", "en-US"])).toBe("RU");
    expect(countryFromLanguages(["en", "pt-BR"])).toBe("BR");
  });

  it("suggests nothing without a known region", () => {
    expect(countryFromLanguages(["en", "de"])).toBeNull();
    expect(countryFromLanguages(["es-419", "not a tag"])).toBeNull();
  });
});

describe("needsCrossBorderConsent", () => {
  it("asks only for an account in Russia", () => {
    expect(needsCrossBorderConsent("RU")).toBe(true);
    expect(needsCrossBorderConsent("NL")).toBe(false);
    expect(needsCrossBorderConsent(null)).toBe(false);
  });
});

it("lists every code once", () => {
  expect(new Set(COUNTRY_CODES).size).toBe(COUNTRY_CODES.length);
});
