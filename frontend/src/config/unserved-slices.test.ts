import { afterEach, describe, expect, it, vi } from "vitest";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("isServed", () => {
  it("hides only a listed slice when no mocks answer for it", async () => {
    vi.stubEnv("MODE", "api");
    const { isServed } = await import("./unserved-slices");

    expect(isServed("hubs")).toBe(false);
    expect(isServed("notes")).toBe(true);
  });

  it("keeps every slice while the development mocks answer", async () => {
    vi.stubEnv("MODE", "development");
    const { isServed } = await import("./unserved-slices");

    expect(isServed("hubs")).toBe(true);
  });
});
