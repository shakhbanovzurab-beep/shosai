import { globSync, readFileSync } from "node:fs";
import { join, sep } from "node:path";

import type { SourceFile } from "./sourceModules";

// Код приложения и тестовая сборка для стенда паритета; тесты правилам не подчиняются.
const SOURCE_PATTERNS = ["src/**/*.{ts,tsx}", "parity-build/**/*.{ts,tsx}"];

/** Читает исходники проекта из каталога `frontend/`. Объявления типов (`.d.ts`) не код. */
export function readProjectSources(frontendRoot: string): SourceFile[] {
  return globSync(SOURCE_PATTERNS, { cwd: frontendRoot })
    .filter((path) => !path.endsWith(".d.ts"))
    .map((path) => ({
      path: path.split(sep).join("/"),
      text: readFileSync(join(frontendRoot, path), "utf8"),
    }))
    .toSorted((left, right) => left.path.localeCompare(right.path));
}
