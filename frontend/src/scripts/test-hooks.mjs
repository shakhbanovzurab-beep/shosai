// Lets `node --test` run the TypeScript unit tests as the app imports them: "@/…" aliases and
// extensionless relative imports. Node strips the types itself. Run: npm test
import { existsSync } from "node:fs";
import { registerHooks } from "node:module";
import { fileURLToPath } from "node:url";

const SRC = new URL("../", import.meta.url);
const EXTENSIONS = [".ts", ".tsx", "/index.ts"];

registerHooks({
  resolve(specifier, context, nextResolve) {
    const target = specifier.startsWith("@/") ? new URL(specifier.slice(2), SRC).href : specifier;
    const relative = target.startsWith(".") || target.startsWith("file:");
    if (relative && !/\.[cm]?[jt]sx?$/.test(target)) {
      const base = new URL(target, context.parentURL).href;
      for (const extension of EXTENSIONS) {
        const candidate = `${base}${extension}`;
        if (existsSync(fileURLToPath(candidate))) return nextResolve(candidate, context);
      }
    }
    return nextResolve(target, context);
  },
});
