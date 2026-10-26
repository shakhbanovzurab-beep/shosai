import { describe, expect, it } from "vitest";

import { mermaidWithoutElk } from "./mermaid-without-elk";

const plugin = mermaidWithoutElk();
const hook = <T>(value: unknown) => (typeof value === "function" ? value : (value as { handler: T }).handler) as T;
const resolveId = hook<(source: string, importer?: string) => string | null>(plugin.resolveId);
const load = hook<(id: string) => string | null>(plugin.load);
const MERMAID = "/app/node_modules/mermaid/dist/chunks/mermaid.core/chunk-EJLWFMJV.mjs";

describe("mermaidWithoutElk", () => {
  it("replaces only Mermaid's ELK chunk, in the build", () => {
    expect(plugin.apply).toBe("build");
    const stub = resolveId("./elk-QONTBCTQ.mjs", MERMAID);
    expect(stub).not.toBeNull();
    expect(resolveId("./dagre-NK4GIZVX.mjs", MERMAID)).toBeNull();
    expect(resolveId("./elk-QONTBCTQ.mjs", "/app/src/features/leo/ui/markdown/diagram-render.ts")).toBeNull();
    expect(resolveId("./elk-QONTBCTQ.mjs")).toBeNull();
  });

  it("loads a module whose layout refuses, so loading itself never fails", () => {
    const stub = resolveId("./elk-QONTBCTQ.mjs", MERMAID) ?? "";
    const code = load(stub) ?? "";
    expect(code).toContain("export const render = async");
    expect(code).toContain("throw new Error");
    expect(code.trimStart().startsWith("throw")).toBe(false);
    expect(load("/app/src/main.tsx")).toBeNull();
  });
});
