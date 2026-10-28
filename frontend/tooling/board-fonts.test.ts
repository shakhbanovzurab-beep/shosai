import { describe, expect, it } from "vitest";

import { fontFile, fontsDirectory } from "./board-fonts";
import { readdirSync } from "node:fs";

const root = fontsDirectory();

describe("boardFonts", () => {
  it("finds Excalidraw's fonts in the package", () => {
    expect(readdirSync(root)).toContain("Excalifont");
  });

  it("answers a font inside the directory and nothing outside it", () => {
    const [font] = readdirSync(`${root}/Excalifont`);
    expect(fontFile(root, `/Excalifont/${font}?v=1`)).toBe(`${root}/Excalifont/${font}`);
    expect(fontFile(root, "/Excalifont/missing.woff2")).toBeNull();
    expect(fontFile(root, "/../package.json")).toBeNull();
    expect(fontFile(root, "/%2e%2e/package.json")).toBeNull();
    expect(fontFile(root, "/")).toBeNull();
  });
});
